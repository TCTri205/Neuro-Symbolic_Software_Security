import ast
import os
import logging
from typing import List, Optional

from src.core.context.loader import ProjectContext
from src.plugins.base import FrameworkPlugin, Route

logger = logging.getLogger(__name__)


class DjangoPlugin(FrameworkPlugin):
    @property
    def name(self) -> str:
        return "django"

    def detect(self, context: ProjectContext) -> bool:
        """
        Detect Django by checking pyproject.toml dependencies or settings.
        """
        if context.pyproject and "project" in context.pyproject:
            deps = context.pyproject["project"].get("dependencies", [])
            if any("django" in d.lower() for d in deps):
                return True

        if context.settings and "ROOT_URLCONF" in context.settings:
            return True

        return False

    def parse_routes(self, project_path: str) -> List[Route]:
        """
        Scan for urls.py files and parse urlpatterns.
        """
        routes = []
        for root, _, files in os.walk(project_path):
            for file in files:
                # Naive check for url conf files
                if file == "urls.py" or (file.endswith(".py") and "urls" in file):
                    full_path = os.path.join(root, file)
                    routes.extend(self._parse_urls_file(full_path, project_path))
        return routes

    def _parse_urls_file(self, file_path: str, project_root: str) -> List[Route]:
        routes = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)

            # Find assignment to "urlpatterns"
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "urlpatterns":
                            if isinstance(node.value, ast.List):
                                for item in node.value.elts:
                                    route = self._extract_route_from_path_call(
                                        item, file_path, project_root
                                    )
                                    if route:
                                        routes.append(route)
        except Exception as e:
            logger.debug(f"Error parsing {file_path}: {e}")
        return routes

    def _extract_route_from_path_call(
        self, node: ast.AST, file_path: str, project_root: str
    ) -> Optional[Route]:
        # Expecting path('pattern', view) or re_path
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in (
                "path",
                "re_path",
                "url",
            ):
                args = node.args
                if len(args) >= 2:
                    pattern = "/"
                    if isinstance(args[0], ast.Constant) and isinstance(
                        args[0].value, str
                    ):
                        pattern = args[0].value

                    handler_node = args[1]
                    handler_name = self._resolve_handler_name(handler_node)

                    rel_path = os.path.relpath(file_path, project_root)
                    return Route(
                        path=pattern,
                        method="ALL",  # Django routes handle all methods by default unless restricted in view
                        handler=handler_name,
                        metadata={
                            "source_file": rel_path,
                            "django_func": node.func.id,
                            "line": node.lineno,
                        },
                    )
        return None

    def _resolve_handler_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._resolve_handler_name(node.value)}.{node.attr}"
        if isinstance(node, ast.Call):
            # possibly include() or view.as_view()
            if isinstance(node.func, ast.Attribute) and node.func.attr == "as_view":
                return f"{self._resolve_handler_name(node.func.value)}.as_view"
            if isinstance(node.func, ast.Name) and node.func.id == "include":
                return "include(...)"
        return "unknown"
