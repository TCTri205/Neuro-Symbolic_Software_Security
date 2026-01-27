from pydantic import BaseModel
from src.core.ai.decoder import ConstrainedDecoder
import pytest


class SampleModel(BaseModel):
    name: str
    age: int


class TestConstrainedDecoder:
    def test_decode_valid_json(self):
        text = '{"name": "Alice", "age": 30}'
        obj = ConstrainedDecoder.decode(text, SampleModel)
        assert obj.name == "Alice"
        assert obj.age == 30

    def test_decode_markdown_json(self):
        text = """
```json
{
    "name": "Bob",
    "age": 25
}
```
"""
        obj = ConstrainedDecoder.decode(text, SampleModel)
        assert obj.name == "Bob"
        assert obj.age == 25

    def test_decode_invalid_json(self):
        text = "{name: Alice}"  # Invalid JSON
        with pytest.raises(ValueError, match="Failed to parse JSON"):
            ConstrainedDecoder.decode(text, SampleModel)

    def test_decode_invalid_schema(self):
        text = '{"name": "Alice", "age": "thirty"}'  # Invalid type
        with pytest.raises(ValueError, match="Output does not match schema"):
            ConstrainedDecoder.decode(text, SampleModel)
