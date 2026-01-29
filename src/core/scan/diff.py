import os
import subprocess
import logging
from typing import List, Set, Dict, Optional
from src.core.persistence.graph_serializer import (
    GraphPersistenceService,
)
from src.core.parser.ir import IRGraph

logger = logging.getLogger(__name__)


class DiffScanner:
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        self.persistence = GraphPersistenceService()

    def get_changed_files(self, base_ref: str = "origin/main") -> List[str]:
        """
        Identify changed files between base_ref and HEAD using git.
        """
        try:
            # Check if base_ref exists
            subprocess.run(
                ["git", "rev-parse", "--verify", base_ref],
                cwd=self.project_root,
                check=True,
                capture_output=True,
            )

            # Run diff
            cmd = ["git", "diff", "--name-only", f"{base_ref}...HEAD"]
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True,
            )

            files = [
                f.strip()
                for f in result.stdout.splitlines()
                if f.strip().endswith(".py")
            ]
            return [os.path.join(self.project_root, f) for f in files]

        except subprocess.CalledProcessError as e:
            logger.warning(
                f"Git diff failed: {e}. Falling back to full scan suggestion."
            )
            return []
        except FileNotFoundError:
            logger.warning("Git not found. Cannot perform diff scan.")
            return []

    def compute_impacted_files(self, changed_files: List[str]) -> Set[str]:
        """
        Compute the set of files that need re-scanning based on changes and dependencies.
        """
        if not changed_files:
            return set()

        # Load existing graph to build dependency map
        loaded = self.persistence.load_project_graph(self.project_root, strict=True)
        if not loaded:
            logger.warning("No fresh graph cache found. Returning only changed files.")
            return set(changed_files)

        graph, _ = loaded

        impact_map = self._build_impact_map(graph)

        impacted_set = set(changed_files)
        queue = list(changed_files)

        processed = set(changed_files)

        while queue:
            current_file = queue.pop(0)

            # Find files that depend on current_file
            dependents = impact_map.get(current_file, set())

            for dep in dependents:
                if dep not in processed:
                    processed.add(dep)
                    impacted_set.add(dep)
                    queue.append(dep)

        return impacted_set

    def _build_impact_map(self, graph: IRGraph) -> Dict[str, Set[str]]:
        """
        Build a reverse dependency map: imported_file -> {dependent_files}.
        """
        # Map: dependency -> {dependents}
        impact_map: Dict[str, Set[str]] = {}

        # Helper to normalize paths
        def norm_path(p: str) -> str:
            return os.path.abspath(os.path.join(self.project_root, p))

        # We iterate over nodes to find Imports
        # IR Schema:
        # Import: names (list of aliases), asnames
        # ImportFrom: module, names, asnames, level

        for node in graph.nodes:
            if not node.span or not node.span.file:
                continue

            current_file = norm_path(node.span.file)
            imported_modules = []

            if node.kind == "Import":
                # attrs["names"] is list of module names
                names = node.attrs.get("names", [])
                imported_modules.extend(names)

            elif node.kind == "ImportFrom":
                module = node.attrs.get("module")
                if module:
                    imported_modules.append(module)
                # We could also check names for relative imports if module is None?
                # But typically 'module' is set for 'from X import Y'

            for mod_name in imported_modules:
                resolved_path = self._resolve_module_path(mod_name)
                if resolved_path:
                    if resolved_path not in impact_map:
                        impact_map[resolved_path] = set()
                    impact_map[resolved_path].add(current_file)

        return impact_map

    def _resolve_module_path(self, module_name: str) -> Optional[str]:
        """
        Resolve a dotted module name to an absolute file path.
        Assumes standard src layout and python structure.
        """
        # Simple heuristic: replace . with / and add .py
        # Check if file exists relative to project root

        # Try direct mapping: src.core.utils -> src/core/utils.py
        rel_path = module_name.replace(".", os.sep) + ".py"
        abs_path = os.path.join(self.project_root, rel_path)
        if os.path.exists(abs_path):
            return abs_path

        # Try package mapping: src.core -> src/core/__init__.py
        rel_path_init = os.path.join(module_name.replace(".", os.sep), "__init__.py")
        abs_path_init = os.path.join(self.project_root, rel_path_init)
        if os.path.exists(abs_path_init):
            return abs_path_init

        return None
