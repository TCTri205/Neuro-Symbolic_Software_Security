import ast
import os
import logging
from typing import List, Optional

from src.core.context.loader import ProjectContext
from src.plugins.base import FrameworkPlugin, Route

logger = logging.getLogger(__name__)


class FlaskPlugin(FrameworkPlugin):
    @property
    def name(self) -> str:
        return "flask"

    def detect(self, context: ProjectContext) -> bool:
        """
        Detect Flask by checking pyproject.toml dependencies.
        """
        if context.pyproject and "project" in context.pyproject:
            deps = context.pyproject["project"].get("dependencies", [])
            # Also check optional-dependencies if needed, but let's start with main deps
            if any("flask" in d.lower() for d in deps):
                return True

        # Also check for poetry style dependencies
        if context.pyproject and "tool" in context.pyproject:
            poetry_deps = (
                context.pyproject["tool"].get("poetry", {}).get("dependencies", {})
            )
            if "flask" in poetry_deps or "Flask" in poetry_deps:
                return True

        return False

    def parse_routes(self, project_path: str) -> List[Route]:
        """
        Scan for @app.route() or @bp.route() decorators.
        """
        routes = []
        for root, _, files in os.walk(project_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    file_routes = self._parse_file(full_path, project_path)
                    routes.extend(file_routes)
        return routes

    def _parse_file(self, file_path: str, project_root: str) -> List[Route]:
        routes = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        if self._is_route_decorator(decorator):
                            route = self._extract_route_info(
                                decorator, node, file_path, project_root
                            )
                            if route:
                                routes.append(route)
        except Exception as e:
            logger.debug(f"Failed to parse {file_path}: {e}")
        return routes

    def _is_route_decorator(self, node: ast.AST) -> bool:
        """Check if decorator is a route definition (app.route or bp.route)."""
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                # Matches @*.route(...)
                return node.func.attr == "route"
        return False

    def _extract_route_info(
        self,
        decorator: ast.Call,
        func_node: ast.FunctionDef,
        file_path: str,
        project_root: str,
    ) -> Optional[Route]:
        try:
            path = "/"
            methods = ["GET"]  # Flask default

            # 1. Extract path (first arg)
            if decorator.args:
                arg0 = decorator.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    path = arg0.value

            # 2. Extract methods (keyword arg)
            for keyword in decorator.keywords:
                if keyword.arg == "methods":
                    if isinstance(keyword.value, ast.List):
                        methods = []
                        for elt in keyword.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                methods.append(elt.value)

            rel_path = os.path.relpath(file_path, project_root)

            return Route(
                path=path,
                method=",".join(sorted(methods)),
                handler=func_node.name,
                metadata={
                    "source_file": rel_path,
                    "line": func_node.lineno,
                    "framework": "flask",
                },
            )
        except Exception as e:
            logger.warning(f"Error extracting route info in {file_path}: {e}")
            return None
