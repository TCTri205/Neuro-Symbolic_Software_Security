from __future__ import annotations

import ast
import os
import tomllib
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ProjectContext:
    env_vars: Dict[str, str] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    docker: Optional[str] = None
    pyproject: Dict[str, Any] = field(default_factory=dict)


class ContextLoader:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def load(self) -> ProjectContext:
        return ProjectContext(
            env_vars=self._load_env(),
            settings=self._load_settings(),
            docker=self._load_docker(),
            pyproject=self._load_pyproject(),
        )

    def _load_env(self) -> Dict[str, str]:
        path = os.path.join(self.root_dir, ".env")
        if not os.path.exists(path):
            return {}

        env_vars = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
        except Exception:
            pass
        return env_vars

    def _load_settings(self) -> Dict[str, Any]:
        """Safely extract variables from settings.py using AST."""
        path = os.path.join(self.root_dir, "settings.py")
        if not os.path.exists(path):
            return {}

        settings = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source)
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            try:
                                value = ast.literal_eval(node.value)
                                settings[target.id] = value
                            except Exception:
                                # Skip values that can't be safely evaluated (e.g. calls)
                                pass
        except Exception:
            pass
        return settings

    def _load_docker(self) -> Optional[str]:
        path = os.path.join(self.root_dir, "Dockerfile")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    def _load_pyproject(self) -> Dict[str, Any]:
        path = os.path.join(self.root_dir, "pyproject.toml")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "rb") as f:
                return tomllib.load(f)
        except Exception:
            return {}
