from typing import List, Dict, Set, Optional, Any, Tuple
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


class TaintSpan(BaseModel):
    start_line: int
    start_col: int
    end_line: int
    end_col: int


class TaintFlow(BaseModel):
    source: str
    sink: str
    path: List[str] = Field(
        default_factory=list
    )  # List of SSA versions or statement IDs
    implicit: bool = False
    sink_span: Optional[TaintSpan] = None


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
        source_versions: Set[str] = set()
        worklist: List[str] = []

        stmt_blocks = self._build_statement_blocks(cfg)
        control_successors = self._build_control_successors(cfg)
        control_tainted: Set[Tuple[int, str]] = set()
        control_regions_cache: Dict[int, Set[int]] = {}
        implicit_versions: Set[str] = set()

        version_defs = self._build_version_definitions(cfg, ssa_map)

        # 1. Sources
        for block in cfg._blocks.values():
            for stmt in block.statements:
                source_name = self._get_source_name(stmt, config)
                if source_name:
                    defined_vars = self._get_defined_vars(stmt, ssa_map)
                    for ver in defined_vars:
                        if ver not in taint_provenance:
                            taint_provenance[ver] = source_name
                            source_versions.add(ver)
                            worklist.append(ver)

        # 2. Propagate
        while worklist:
            ver = worklist.pop(0)
            source = taint_provenance[ver]
            is_implicit = ver in implicit_versions

            # Stmt uses
            uses = version_uses.get(ver, [])
            for stmt in uses:
                if self._is_sanitizer_stmt(stmt, config):
                    continue
                defined_vars = self._get_defined_vars(stmt, ssa_map)
                for new_ver in defined_vars:
                    if new_ver not in taint_provenance:
                        taint_provenance[new_ver] = source
                        if is_implicit:
                            implicit_versions.add(new_ver)
                        worklist.append(new_ver)

                block_id = stmt_blocks.get(stmt)
                if block_id is not None and self._is_control_stmt(
                    stmt, block_id, control_successors
                ):
                    self._apply_control_taint(
                        cfg,
                        ssa_map,
                        block_id,
                        source,
                        taint_provenance,
                        worklist,
                        control_successors,
                        control_tainted,
                        control_regions_cache,
                        implicit_versions,
                    )

            # Phi uses
            for block in cfg._blocks.values():
                for phi in block.phi_nodes:
                    if ver in phi.operands.values():
                        if phi.result not in taint_provenance:
                            taint_provenance[phi.result] = source
                            if ver in implicit_versions:
                                implicit_versions.add(phi.result)
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
                        paths = self._build_backward_paths(
                            arg_ver,
                            taint_provenance,
                            version_defs,
                            ssa_map,
                            source_versions,
                        )
                        for path in paths:
                            results.append(
                                TaintFlow(
                                    source=src_name,
                                    sink=sink_name,
                                    path=path,
                                    implicit=any(
                                        ver in implicit_versions for ver in path
                                    ),
                                    sink_span=self._span_from_node(stmt),
                                )
                            )

        return results

    def _build_statement_blocks(self, cfg: ControlFlowGraph) -> Dict[ast.AST, int]:
        stmt_blocks: Dict[ast.AST, int] = {}
        for block in cfg._blocks.values():
            for stmt in block.statements:
                stmt_blocks[stmt] = block.id
        return stmt_blocks

    def _build_control_successors(self, cfg: ControlFlowGraph) -> Dict[int, List[int]]:
        control_labels = {
            "True",
            "False",
            "Next",
            "Stop",
            "AsyncNext",
            "AsyncStop",
        }
        control_successors: Dict[int, List[int]] = {}
        for source, target, data in cfg.graph.edges(data=True):
            label = data.get("label") if data else None
            if label in control_labels:
                control_successors.setdefault(source, []).append(target)
        return control_successors

    def _is_control_stmt(
        self,
        stmt: ast.AST,
        block_id: int,
        control_successors: Dict[int, List[int]],
    ) -> bool:
        if block_id not in control_successors:
            return False
        return not isinstance(stmt, ast.stmt)

    def _apply_control_taint(
        self,
        cfg: ControlFlowGraph,
        ssa_map: Dict[ast.AST, str],
        block_id: int,
        source: str,
        taint_provenance: Dict[str, str],
        worklist: List[str],
        control_successors: Dict[int, List[int]],
        control_tainted: Set[Tuple[int, str]],
        control_regions_cache: Dict[int, Set[int]],
        implicit_versions: Set[str],
    ) -> None:
        succs = control_successors.get(block_id)
        if not succs:
            return

        if block_id not in control_regions_cache:
            control_regions_cache[block_id] = self._compute_control_region(cfg, succs)

        for tainted_block_id in control_regions_cache[block_id]:
            if (tainted_block_id, source) in control_tainted:
                continue
            control_tainted.add((tainted_block_id, source))
            block = cfg.get_block(tainted_block_id)
            if not block:
                continue
            for stmt in block.statements:
                defined_vars = self._get_defined_vars(stmt, ssa_map)
                for new_ver in defined_vars:
                    if new_ver not in taint_provenance:
                        taint_provenance[new_ver] = source
                        implicit_versions.add(new_ver)
                        worklist.append(new_ver)

    def _compute_control_region(
        self, cfg: ControlFlowGraph, succs: List[int]
    ) -> Set[int]:
        reachable_sets: List[Set[int]] = []
        for succ in succs:
            reachable_sets.append(self._collect_reachable(cfg, succ, set()))

        if not reachable_sets:
            return set()

        join_nodes = set.intersection(*reachable_sets)
        region: Set[int] = set()
        for succ in succs:
            region.update(self._collect_reachable(cfg, succ, join_nodes))
        return region

    def _collect_reachable(
        self, cfg: ControlFlowGraph, start: int, stop_nodes: Set[int]
    ) -> Set[int]:
        visited: Set[int] = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node in visited or node in stop_nodes:
                continue
            visited.add(node)
            for succ in cfg.graph.successors(node):
                if succ not in visited:
                    stack.append(succ)
        return visited

    def _build_version_definitions(
        self, cfg: ControlFlowGraph, ssa_map: Dict[ast.AST, str]
    ) -> Dict[str, Any]:
        version_defs: Dict[str, Any] = {}
        for block in cfg._blocks.values():
            for phi in block.phi_nodes:
                version_defs[phi.result] = phi
            for stmt in block.statements:
                defined_vars = self._get_defined_vars(stmt, ssa_map)
                for ver in defined_vars:
                    version_defs[ver] = stmt
        return version_defs

    def _build_backward_paths(
        self,
        start_ver: str,
        taint_provenance: Dict[str, str],
        version_defs: Dict[str, Any],
        ssa_map: Dict[ast.AST, str],
        source_versions: Set[str],
    ) -> List[List[str]]:
        paths: List[List[str]] = []

        def dfs(ver: str, path: List[str], visiting: Set[str]):
            if ver in visiting:
                return
            if ver not in taint_provenance:
                return

            visiting.add(ver)
            path.append(ver)

            if ver in source_versions:
                paths.append(list(reversed(path)))
            else:
                def_node = version_defs.get(ver)
                if isinstance(def_node, ast.AST):
                    used_versions = self._get_used_versions(def_node, ssa_map)
                    tainted_used = [u for u in used_versions if u in taint_provenance]
                    if tainted_used:
                        for used in tainted_used:
                            dfs(used, path, visiting)
                    else:
                        paths.append(list(reversed(path)))
                elif def_node is not None and hasattr(def_node, "operands"):
                    operands = def_node.operands.values()
                    tainted_operands = [o for o in operands if o in taint_provenance]
                    if tainted_operands:
                        for op in tainted_operands:
                            dfs(op, path, visiting)
                    else:
                        paths.append(list(reversed(path)))
                else:
                    paths.append(list(reversed(path)))

            path.pop()
            visiting.remove(ver)

        dfs(start_ver, [], set())
        return paths

    def _scan_uses(self, stmt: ast.AST, ssa_map: Dict[ast.AST, str], callback):
        """
        Recursively find all Name load nodes in the statement and register them.
        """
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node in ssa_map:
                    callback(ssa_map[node], stmt)
            # Handle other nodes if necessary (e.g. attributes)

    def _get_used_versions(
        self, stmt: ast.AST, ssa_map: Dict[ast.AST, str]
    ) -> List[str]:
        used_versions: List[str] = []

        def register_use(ver: str, s: ast.AST):
            used_versions.append(ver)

        self._scan_uses(stmt, ssa_map, register_use)
        return used_versions

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

    def _span_from_node(self, node: ast.AST) -> Optional[TaintSpan]:
        start_line = getattr(node, "lineno", -1)
        start_col = getattr(node, "col_offset", -1)
        end_line = getattr(node, "end_lineno", None)
        end_col = getattr(node, "end_col_offset", None)

        if not isinstance(start_line, int) or not isinstance(start_col, int):
            return None

        if not isinstance(end_line, int):
            end_line = start_line
        if not isinstance(end_col, int):
            end_col = start_col + 1

        return TaintSpan(
            start_line=start_line,
            start_col=start_col,
            end_line=end_line,
            end_col=end_col,
        )
