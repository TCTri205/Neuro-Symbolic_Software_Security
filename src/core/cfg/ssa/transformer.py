import ast
import networkx as nx
from typing import Dict, Set, List, DefaultDict, Any, Union, Optional
from collections import defaultdict
from ..models import ControlFlowGraph, PhiNode


class SSATransformer:
    def __init__(self, cfg: ControlFlowGraph):
        self.cfg = cfg
        self.dom_tree = None
        self.dom_frontiers = None
        self.dom_children = defaultdict(list)

        # Mapping from variable name to list of block IDs defining it
        self.defs: DefaultDict[str, Set[int]] = defaultdict(set)
        # Set of all variable names encountered
        self.vars: Set[str] = set()

        # SSA State
        self.counters: Dict[str, int] = defaultdict(int)
        self.stacks: Dict[str, List[str]] = defaultdict(list)

        # Result: Map AST node (Name or arg) to SSA version string (e.g., "x_1")
        self.ssa_map: Dict[ast.AST, str] = {}

        # Reverse Map: SSA version string -> Definition AST Node (or PhiNode)
        self.version_defs: Dict[str, Any] = {}

    def analyze(self):
        if not self.cfg.entry_block:
            return

        # 1. Compute Dominance
        self.compute_dominance()

        # 2. Find Assignments (Defs)
        self.find_defs()

        # 3. Insert Phi Nodes
        self.insert_phi_nodes()

        # 4. Rename Variables
        self.rename(self.cfg.entry_block.id)

    def compute_dominance(self):
        start = self.cfg.entry_block.id
        # Compute dominance frontiers
        self.dom_frontiers = nx.dominance_frontiers(self.cfg.graph, start)
        # Compute immediate dominator tree
        self.dom_tree = nx.immediate_dominators(self.cfg.graph, start)

        # Build children map for traversal
        for node, parent in self.dom_tree.items():
            if node != parent:
                self.dom_children[parent].append(node)

    def find_defs(self):
        for block in self.cfg._blocks.values():
            for stmt in block.statements:
                self._extract_defs_from_stmt(stmt, block.id)

    def _extract_defs_from_stmt(self, node: ast.AST, block_id: int):
        # We only care about finding WHICH variables are defined in WHICH blocks
        # to place Phi nodes.
        targets = []
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets.append(node.target)
        elif isinstance(node, ast.arg):
            self.defs[node.arg].add(block_id)
            self.vars.add(node.arg)
            return
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            targets.append(node.target)

        # Helper to recursively find names in targets (e.g. tuples)
        self._find_names_in_targets(targets, block_id)

    def _find_names_in_targets(self, targets: List[ast.AST], block_id: int):
        for t in targets:
            if isinstance(t, ast.Name):
                self.defs[t.id].add(block_id)
                self.vars.add(t.id)
            elif isinstance(t, (ast.Tuple, ast.List)):
                self._find_names_in_targets(t.elts, block_id)
            # Add other unpacking structures if needed

    def insert_phi_nodes(self):
        for v in self.vars:
            worklist = list(self.defs[v])
            has_phi = set()
            processed_work = set(worklist)

            while worklist:
                b = worklist.pop(0)
                processed_work.discard(b)

                for df_node in self.dom_frontiers.get(b, []):
                    if df_node not in has_phi:
                        # Insert Phi
                        block = self.cfg.get_block(df_node)
                        if block:
                            phi = PhiNode(
                                var_name=v, result=v
                            )  # result temp, will rename later
                            block.add_phi(phi)
                            has_phi.add(df_node)

                            if df_node not in self.defs[v]:
                                self.defs[v].add(df_node)
                                worklist.append(df_node)
                                processed_work.add(df_node)

    def rename(self, block_id: int):
        block = self.cfg.get_block(block_id)
        if not block:
            return

        pushed_counts = defaultdict(int)

        # 1. Handle Phis (Defs)
        for phi in block.phi_nodes:
            new_ver = self._new_version(phi.var_name, pushed_counts, phi, phi)
            phi.result = new_ver

        # 2. Handle Statements
        for stmt in block.statements:
            if isinstance(stmt, ast.Assign):
                self._rename_uses_recursive(stmt.value)
                for t in stmt.targets:
                    self._rename_defs_recursive(t, pushed_counts, stmt)

            elif isinstance(stmt, ast.AnnAssign):
                if stmt.value:
                    self._rename_uses_recursive(stmt.value)
                self._rename_defs_recursive(stmt.target, pushed_counts, stmt)

            elif isinstance(stmt, ast.AugAssign):
                # x += 1 => x_2 = x_1 + 1
                # Target acts as use first
                self._rename_uses_recursive(stmt.target)
                self._rename_uses_recursive(stmt.value)
                self._rename_defs_recursive(stmt.target, pushed_counts, stmt)

            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                self._rename_uses_recursive(stmt.iter)
                self._rename_defs_recursive(stmt.target, pushed_counts, stmt)

            elif isinstance(stmt, ast.arg):
                self._rename_defs_recursive(stmt, pushed_counts, stmt)

            else:
                # Expressions, etc.
                # Special case: If it's a Name with Store context, treat as Def
                # (e.g. loop var in decomposed CFG where target is added as a stmt)
                if isinstance(stmt, ast.Name) and isinstance(stmt.ctx, ast.Store):
                    self._rename_defs_recursive(stmt, pushed_counts, stmt)
                else:
                    self._rename_uses_recursive(stmt)

        # 3. Update Successor Phi Inputs
        for succ_id in self.cfg.graph.successors(block_id):
            succ_block = self.cfg.get_block(succ_id)
            for phi in succ_block.phi_nodes:
                name = phi.var_name
                if self.stacks[name]:
                    phi.operands[block_id] = self.stacks[name][-1]
                else:
                    phi.operands[block_id] = f"{name}_undefined"

        # 4. Recurse
        for child in self.dom_children[block_id]:
            self.rename(child)

        # 5. Pop Stacks
        for name, count in pushed_counts.items():
            for _ in range(count):
                self.stacks[name].pop()

    def _new_version(
        self,
        name: str,
        pushed_counts: Dict[str, int],
        def_node: Any,
        stmt: Optional[Any] = None,
    ) -> str:
        self.counters[name] += 1
        ver = f"{name}_{self.counters[name]}"
        self.stacks[name].append(ver)
        pushed_counts[name] += 1
        self.version_defs[ver] = (def_node, stmt)
        return ver

    def _rename_uses_recursive(self, node: ast.AST):
        """Recursively find loads and map them to current stack top."""
        if isinstance(node, ast.Name):
            # Check context? Usually Load if we are here.
            # But AugAssign target is Store context, yet we treat as Use.
            # So just trust the caller.
            if self.stacks[node.id]:
                self.ssa_map[node] = self.stacks[node.id][-1]
            else:
                self.ssa_map[node] = f"{node.id}_undefined"
        elif isinstance(node, ast.arg):
            # Should not happen in uses?
            pass
        else:
            # Recurse
            for child in ast.iter_child_nodes(node):
                self._rename_uses_recursive(child)

    def _rename_defs_recursive(
        self, node: ast.AST, pushed_counts: Dict[str, int], stmt: Optional[Any]
    ):
        """Recursively find stores, create new versions."""
        if isinstance(node, ast.Name):
            new_ver = self._new_version(node.id, pushed_counts, node, stmt)
            self.ssa_map[node] = new_ver
        elif isinstance(node, ast.arg):
            new_ver = self._new_version(node.arg, pushed_counts, node, stmt)
            self.ssa_map[node] = new_ver
        elif isinstance(node, (ast.Tuple, ast.List)):
            for child in node.elts:
                self._rename_defs_recursive(child, pushed_counts, stmt)
