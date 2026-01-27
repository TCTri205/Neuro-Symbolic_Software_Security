from typing import List, Dict, Set, Optional, Any
from pydantic import BaseModel, Field
import ast
from ..cfg.models import ControlFlowGraph


class TaintSource(BaseModel):
    name: str
    kind: str = "function"  # function, attribute, etc.


class TaintSink(BaseModel):
    name: str
    kind: str = "function"


class TaintConfiguration(BaseModel):
    sources: List[TaintSource] = Field(default_factory=list)
    sinks: List[TaintSink] = Field(default_factory=list)
    sanitizers: List[str] = Field(default_factory=list)


class TaintFlow(BaseModel):
    source: str
    sink: str
    path: List[str] = Field(
        default_factory=list
    )  # List of SSA versions or statement IDs


class TaintResult(BaseModel):
    flows: List[TaintFlow] = Field(default_factory=list)


class TaintEngine:
    def __init__(self):
        pass

    def analyze(
        self,
        cfg: ControlFlowGraph,
        ssa_map: Dict[ast.AST, str],
        config: TaintConfiguration,
    ) -> List[TaintFlow]:
        """
        Analyze the CFG for taint flows based on the configuration.
        """
        tainted_versions: Set[str] = set()
        worklist: List[str] = []

        # 1. Indexing: Build a map of SSA version -> Statements using it
        # and SSA version -> Statements defining it (though def is unique usually)
        version_uses: Dict[str, List[ast.AST]] = {}

        # Helper to register use
        def register_use(ver: str, stmt: ast.AST):
            if ver not in version_uses:
                version_uses[ver] = []
            version_uses[ver].append(stmt)

        # Scan all blocks to build index and find initial sources
        for block in cfg._blocks.values():
            if not block:
                continue

            # Handle Phi nodes for propagation
            # Phi(result, operands={block_id: ver})
            # If operand 'ver' is tainted, 'result' becomes tainted.
            # We can treat this as a use of 'ver' defining 'result'.
            for phi in block.phi_nodes:
                for ver in phi.operands.values():
                    # We treat the Phi node as the statement here
                    # But PhiNode is not ast.AST. We need a way to identifying it.
                    # For simplicity, we'll handle Phi propagation separately or wrap it.
                    # Let's add a special handler for Phi in the worklist loop.
                    pass

            for stmt in block.statements:
                # Check for Uses
                self._scan_uses(stmt, ssa_map, register_use)

                # Check for Sources
                source_name = self._get_source_name(stmt, config)
                if source_name:
                    # Found a source call/access.
                    # The target of this assignment is tainted.
                    defined_vars = self._get_defined_vars(stmt, ssa_map)
                    for ver in defined_vars:
                        if ver not in tainted_versions:
                            tainted_versions.add(ver)
                            worklist.append(ver)

        # 2. Propagation
        while worklist:
            ver = worklist.pop(0)

            # Find uses in statements
            uses = version_uses.get(ver, [])
            for stmt in uses:
                # If this statement defines a new variable, taint it.
                defined_vars = self._get_defined_vars(stmt, ssa_map)
                for new_ver in defined_vars:
                    if new_ver not in tainted_versions:
                        tainted_versions.add(new_ver)
                        worklist.append(new_ver)

            # Find uses in Phi nodes
            # Scan all Phis in all blocks? Inefficient.
            # Should have indexed Phis too.
            for block in cfg._blocks.values():
                for phi in block.phi_nodes:
                    if ver in phi.operands.values():
                        if phi.result not in tainted_versions:
                            tainted_versions.add(phi.result)
                            worklist.append(phi.result)

        # 3. Check Sinks
        results: List[TaintFlow] = []
        for block in cfg._blocks.values():
            for stmt in block.statements:
                sink_name = self._get_sink_name(stmt, config)
                if sink_name:
                    # Check if any argument is tainted
                    if self._is_stmt_tainted(stmt, ssa_map, tainted_versions):
                        results.append(
                            TaintFlow(source="unknown", sink=sink_name)
                        )  # TODO: Track specific source

        # Fixup: We need to link specific source to sink.
        # The current set-based approach loses the path.
        # To track path, tainted_versions should map to Source Info.
        # For now, let's just return generic flow as per test expectation.
        # But wait, test expects `flow.source == "source"`.
        # So I need to track the source name.

        return self._analyze_with_provenance(cfg, ssa_map, config, version_uses)

    def _analyze_with_provenance(
        self,
        cfg: ControlFlowGraph,
        ssa_map: Dict[ast.AST, str],
        config: TaintConfiguration,
        version_uses: Dict[str, List[ast.AST]],
    ) -> List[TaintFlow]:
        # Map version -> Source Name (simplification: one source per version)
        taint_provenance: Dict[str, str] = {}
        worklist: List[str] = []

        # 1. Sources
        for block in cfg._blocks.values():
            for stmt in block.statements:
                source_name = self._get_source_name(stmt, config)
                if source_name:
                    defined_vars = self._get_defined_vars(stmt, ssa_map)
                    for ver in defined_vars:
                        if ver not in taint_provenance:
                            taint_provenance[ver] = source_name
                            worklist.append(ver)

        # 2. Propagate
        while worklist:
            ver = worklist.pop(0)
            source = taint_provenance[ver]

            # Stmt uses
            uses = version_uses.get(ver, [])
            for stmt in uses:
                if self._is_sanitizer_stmt(stmt, config):
                    continue
                defined_vars = self._get_defined_vars(stmt, ssa_map)
                for new_ver in defined_vars:
                    if new_ver not in taint_provenance:
                        taint_provenance[new_ver] = source
                        worklist.append(new_ver)

            # Phi uses
            for block in cfg._blocks.values():
                for phi in block.phi_nodes:
                    if ver in phi.operands.values():
                        if phi.result not in taint_provenance:
                            taint_provenance[phi.result] = source
                            worklist.append(phi.result)

        # 3. Sinks
        results = []
        for block in cfg._blocks.values():
            for stmt in block.statements:
                sink_name = self._get_sink_name(stmt, config)
                if sink_name:
                    # Check args
                    tainted_args = self._get_tainted_args(
                        stmt, ssa_map, taint_provenance
                    )
                    for arg_ver, src_name in tainted_args:
                        results.append(
                            TaintFlow(source=src_name, sink=sink_name, path=[arg_ver])
                        )

        return results

    def _scan_uses(self, stmt: ast.AST, ssa_map: Dict[ast.AST, str], callback):
        """
        Recursively find all Name load nodes in the statement and register them.
        """
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node in ssa_map:
                    callback(ssa_map[node], stmt)
            # Handle other nodes if necessary (e.g. attributes)

    def _get_defined_vars(
        self, stmt: ast.AST, ssa_map: Dict[ast.AST, str]
    ) -> List[str]:
        defs = []
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                self._collect_defs(target, ssa_map, defs)
        elif isinstance(stmt, (ast.AnnAssign, ast.AugAssign)):
            self._collect_defs(stmt.target, ssa_map, defs)
        return defs

    def _collect_defs(self, node: ast.AST, ssa_map: Dict[ast.AST, str], acc: List[str]):
        if isinstance(node, ast.Name):
            if node in ssa_map:
                acc.append(ssa_map[node])
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                self._collect_defs(elt, ssa_map, acc)

    def _get_source_name(
        self, stmt: ast.AST, config: TaintConfiguration
    ) -> Optional[str]:
        # Check if stmt is assignment from a source
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            return self._check_call(stmt.value, config.sources)
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            # Sometimes source is just called? Unlikely to taint anything unless it's a side effect.
            return self._check_call(stmt.value, config.sources)
        return None

    def _get_sink_name(
        self, stmt: ast.AST, config: TaintConfiguration
    ) -> Optional[str]:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            return self._check_call(stmt.value, config.sinks)
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            return self._check_call(stmt.value, config.sinks)
        return None

    def _is_sanitizer_stmt(self, stmt: ast.AST, config: TaintConfiguration) -> bool:
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            return self._check_call(stmt.value, config.sanitizers) is not None
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.value, ast.Call):
            return self._check_call(stmt.value, config.sanitizers) is not None
        if isinstance(stmt, ast.AugAssign) and isinstance(stmt.value, ast.Call):
            return self._check_call(stmt.value, config.sanitizers) is not None
        return False

    def _check_call(self, call: ast.Call, candidates: List[Any]) -> Optional[str]:
        name = self._get_call_name(call)
        if not name:
            return None
        for c in candidates:
            candidate_name = c.name if hasattr(c, "name") else c
            if candidate_name == name:
                return name
        return None

    def _get_call_name(self, call: ast.Call) -> Optional[str]:
        if isinstance(call.func, ast.Name):
            return call.func.id
        if isinstance(call.func, ast.Attribute):
            return self._format_attribute(call.func)
        return None

    def _format_attribute(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Attribute):
            base = self._format_attribute(node.value)
            if base is None:
                return None
            return f"{base}.{node.attr}"
        if isinstance(node, ast.Name):
            return node.id
        return None

    def _is_stmt_tainted(
        self, stmt: ast.AST, ssa_map: Dict[ast.AST, str], tainted_set: Set[str]
    ) -> bool:
        # Check if any use in stmt is tainted
        tainted = False

        def check(ver, s):
            nonlocal tainted
            if ver in tainted_set:
                tainted = True

        self._scan_uses(stmt, ssa_map, check)
        return tainted

    def _get_tainted_args(
        self, stmt: ast.AST, ssa_map: Dict[ast.AST, str], provenance: Dict[str, str]
    ) -> List[tuple]:
        # Returns list of (version, source_name)
        tainted_args = []

        def check(ver, s):
            if ver in provenance:
                tainted_args.append((ver, provenance[ver]))

        self._scan_uses(stmt, ssa_map, check)
        return tainted_args
