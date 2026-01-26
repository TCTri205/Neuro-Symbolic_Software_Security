import pytest
import json
import yaml
from src.core.context.openapi import OpenAPIParser


@pytest.fixture
def sample_openapi_json(tmp_path):
    data = {
        "openapi": "3.0.0",
        "paths": {
            "/users": {
                "get": {
                    "summary": "List users",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/User"},
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                    },
                }
            }
        },
    }
    f = tmp_path / "openapi.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return str(f)


@pytest.fixture
def sample_openapi_yaml(tmp_path):
    data = {
        "openapi": "3.0.0",
        "paths": {
            "/items": {
                "post": {
                    "summary": "Create item",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Item"}
                            }
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "Item": {"type": "object", "properties": {"name": {"type": "string"}}}
            }
        },
    }
    f = tmp_path / "openapi.yaml"
    f.write_text(yaml.dump(data), encoding="utf-8")
    return str(f)


def test_parse_openapi_json(sample_openapi_json):
    parser = OpenAPIParser()
    spec = parser.parse(sample_openapi_json)

    assert spec is not None
    assert "/users" in spec.paths
    assert "get" in spec.paths["/users"]
    assert "User" in spec.schemas
    assert spec.schemas["User"]["properties"]["id"]["type"] == "integer"


def test_parse_openapi_yaml(sample_openapi_yaml):
    parser = OpenAPIParser()
    spec = parser.parse(sample_openapi_yaml)

    assert spec is not None
    assert "/items" in spec.paths
    assert "post" in spec.paths["/items"]
    assert "Item" in spec.schemas


def test_parse_missing_file():
    parser = OpenAPIParser()
    spec = parser.parse("non_existent_file.json")
    assert spec is None


def test_parse_invalid_content(tmp_path):
    f = tmp_path / "invalid.txt"
    f.write_text("not a json or yaml", encoding="utf-8")
    parser = OpenAPIParser()
    spec = parser.parse(str(f))
    # Should probably return None or empty spec
    assert spec is None
