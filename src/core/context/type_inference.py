from typing import Dict, Any, Optional
from src.core.context.openapi import OpenAPISpec


class OpenAPITypeInferrer:
    """
    Infers data types (schemas) for API endpoints based on an OpenAPI specification.
    """

    def __init__(self, spec: OpenAPISpec):
        self.spec = spec

    def resolve_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolves schema references ($ref) to the actual schema definition.
        """
        if not schema:
            return {}

        if "$ref" in schema:
            ref = schema["$ref"]
            return self._resolve_ref(ref)

        # Resolve nested properties if they exist
        if "properties" in schema:
            resolved_props = {}
            for k, v in schema["properties"].items():
                resolved_props[k] = self.resolve_schema(v)
            # Create a copy to avoid modifying the original if it's reused
            schema = schema.copy()
            schema["properties"] = resolved_props

        return schema

    def _resolve_ref(self, ref: str) -> Dict[str, Any]:
        """
        Resolves a JSON pointer reference.
        Currently supports references to #/components/schemas/ and #/definitions/
        """
        # Simple parsing for common OpenAPI patterns
        if ref.startswith("#/components/schemas/"):
            schema_name = ref.split("/")[-1]
            return self.resolve_schema(self.spec.schemas.get(schema_name, {}))

        if ref.startswith("#/definitions/"):
            schema_name = ref.split("/")[-1]
            return self.resolve_schema(self.spec.schemas.get(schema_name, {}))

        return {}

    def infer_request_type(self, path: str, method: str) -> Optional[Dict[str, Any]]:
        """
        Infers the request body schema for a specific endpoint.
        Defaults to application/json content type.
        """
        path_item = self.spec.paths.get(path)
        if not path_item:
            return None

        operation = path_item.get(method.lower())
        if not operation:
            return None

        request_body = operation.get("requestBody")
        if not request_body:
            return None

        content = request_body.get("content", {})
        # Prioritize JSON, but could support others
        json_content = content.get("application/json")
        if not json_content:
            return None

        schema = json_content.get("schema")
        return self.resolve_schema(schema)

    def infer_response_type(
        self, path: str, method: str, status_code: str = "200"
    ) -> Optional[Dict[str, Any]]:
        """
        Infers the response body schema for a specific endpoint and status code.
        Defaults to application/json content type.
        """
        path_item = self.spec.paths.get(path)
        if not path_item:
            return None

        operation = path_item.get(method.lower())
        if not operation:
            return None

        responses = operation.get("responses", {})
        response = responses.get(str(status_code))
        if not response:
            return None

        content = response.get("content", {})
        json_content = content.get("application/json")
        if not json_content:
            return None

        schema = json_content.get("schema")
        return self.resolve_schema(schema)
