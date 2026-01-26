import pytest
from src.core.context.openapi import OpenAPISpec
from src.core.context.type_inference import OpenAPITypeInferrer


@pytest.fixture
def sample_spec():
    return OpenAPISpec(
        version="3.0.0",
        paths={
            "/users": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            },
                        }
                    },
                }
            },
            "/simple": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"schema": {"type": "string"}}
                            }
                        }
                    }
                }
            },
        },
        schemas={
            "User": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                "required": ["name"],
            }
        },
        servers=[],
    )


def test_infer_request_type_with_ref(sample_spec):
    inferrer = OpenAPITypeInferrer(sample_spec)
    schema = inferrer.infer_request_type("/users", "post")

    assert schema is not None
    assert schema["type"] == "object"
    assert "properties" in schema
    assert schema["properties"]["name"]["type"] == "string"


def test_infer_response_type_with_ref(sample_spec):
    inferrer = OpenAPITypeInferrer(sample_spec)
    schema = inferrer.infer_response_type("/users", "post", "201")

    assert schema is not None
    assert schema["type"] == "object"
    assert schema["properties"]["id"]["type"] == "integer"


def test_infer_response_type_simple(sample_spec):
    inferrer = OpenAPITypeInferrer(sample_spec)
    schema = inferrer.infer_response_type("/simple", "get", "200")

    assert schema is not None
    assert schema["type"] == "string"


def test_resolve_schema_direct(sample_spec):
    inferrer = OpenAPITypeInferrer(sample_spec)
    schema = inferrer.resolve_schema({"type": "integer"})
    assert schema["type"] == "integer"


def test_missing_path_or_method(sample_spec):
    inferrer = OpenAPITypeInferrer(sample_spec)
    assert inferrer.infer_request_type("/nonexistent", "get") is None
    assert inferrer.infer_request_type("/users", "delete") is None
