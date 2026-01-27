from pydantic import BaseModel
import pytest
from src.core.ai.validator import StrictJSONValidator


class SampleModel(BaseModel):
    name: str


def test_strict_json_valid():
    text = '{"name": "ok"}'
    obj = StrictJSONValidator.validate(text, SampleModel)
    assert obj.name == "ok"


def test_strict_json_rejects_markdown():
    text = """
```json
{"name": "ok"}
```
"""
    with pytest.raises(ValueError, match="markdown fences"):
        StrictJSONValidator.validate(text, SampleModel)


def test_strict_json_rejects_non_object():
    text = "[1, 2, 3]"
    with pytest.raises(ValueError, match="JSON object"):
        StrictJSONValidator.validate(text, SampleModel)
