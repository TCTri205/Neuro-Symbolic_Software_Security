import json
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


class StrictJSONValidator:
    """
    Validates that a response is strict JSON without wrappers.
    """

    @staticmethod
    def validate(text: str, model_class: Type[T]) -> T:
        raw = text.strip()
        if raw.startswith("```"):
            raise ValueError("Strict JSON required: markdown fences detected")

        if not (raw.startswith("{") and raw.endswith("}")):
            raise ValueError("Strict JSON required: must be a JSON object")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

        try:
            return model_class.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Schema mismatch: {exc}") from exc
