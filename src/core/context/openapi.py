from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import json
import yaml
import os


@dataclass
class OpenAPISpec:
    version: str
    paths: Dict[str, Any] = field(default_factory=dict)
    schemas: Dict[str, Any] = field(default_factory=dict)
    servers: List[Dict[str, Any]] = field(default_factory=list)


class OpenAPIParser:
    """Parses OpenAPI/Swagger specifications (JSON/YAML)."""

    def parse(self, file_path: str) -> Optional[OpenAPISpec]:
        """
        Parses an OpenAPI specification file.

        Args:
            file_path: Absolute path to the file.

        Returns:
            OpenAPISpec object if successful, None otherwise.
        """
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            data = None
            # Try JSON first
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try YAML
                try:
                    data = yaml.safe_load(content)
                except yaml.YAMLError:
                    return None

            if not isinstance(data, dict):
                return None

            # Basic validation: check for 'openapi' or 'swagger' key
            if "openapi" not in data and "swagger" not in data:
                return None

            version = data.get("openapi") or data.get("swagger")

            paths = data.get("paths", {})

            schemas = {}
            # OpenAPI 3.x
            if "components" in data and isinstance(data["components"], dict):
                schemas = data["components"].get("schemas", {})
            # Swagger 2.0
            elif "definitions" in data and isinstance(data["definitions"], dict):
                schemas = data["definitions"]

            servers = data.get("servers", [])

            return OpenAPISpec(
                version=str(version), paths=paths, schemas=schemas, servers=servers
            )

        except Exception:
            return None
