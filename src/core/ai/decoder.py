import json
from typing import Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
import logging

T = TypeVar("T", bound=BaseModel)


class ConstrainedDecoder:
    """
    Enforces structured output from LLM responses by parsing and validating against Pydantic models.
    Can be extended to support 'outlines' or 'guidance' in the future.
    """

    @staticmethod
    def decode(response_text: str, model_class: Type[T]) -> T:
        """
        Parses JSON from response_text and validates it against model_class.
        Raises ValueError if parsing or validation fails.
        """
        try:
            # 1. Clean the response text (often LLMs wrap JSON in ```json ... ```)
            clean_text = ConstrainedDecoder._clean_markdown_json(response_text)

            # 2. Parse JSON
            data = json.loads(clean_text)

            # 3. Validate with Pydantic
            return model_class.model_validate(data)

        except json.JSONDecodeError as e:
            logging.error(f"JSON Decode Error: {e}\nResponse: {response_text}")
            raise ValueError(f"Failed to parse JSON output: {e}")
        except ValidationError as e:
            logging.error(f"Schema Validation Error: {e}\nData: {data}")
            raise ValueError(f"Output does not match schema: {e}")

    @staticmethod
    def _clean_markdown_json(text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
