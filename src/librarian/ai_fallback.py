"""
AI Fallback Profile Builder

This module provides LLM-based profile generation for unknown pure-Python libraries.
When ProfileRegistry and Manual Models have no match, this module uses AI to analyze
library documentation or source code to generate a temporary "shadow profile" with
inferred security labels (Sources, Sinks, Sanitizers).

IMPORTANT: This module MUST NOT be used for C-extension libraries. C-extension behavior
cannot be reliably inferred by AI. Use Manual Models (manual_models.py) for C-extensions.

Usage:
    from src.librarian.ai_fallback import generate_shadow_profile
    from src.core.ai.client import LLMClient

    client = LLMClient(provider="openai")
    library = generate_shadow_profile(
        library_name="unknown_lib",
        version="1.0.0",
        ai_client=client,
        documentation="Library docs here..."
    )
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from src.core.ai.client import AIClient
from src.librarian.models import (
    Library,
    LibraryVersion,
    FunctionSpec,
    SecurityLabel,
)

logger = logging.getLogger(__name__)


# System prompt for LLM - instructs it to act as a security analyst
SYSTEM_PROMPT = """You are a security analysis expert specializing in identifying security-sensitive functions in Python libraries.

Your task is to analyze a Python library and identify functions that are security-relevant:
- **SOURCES**: Functions that return untrusted/tainted data (user input, network data, file reads, environment variables)
- **SINKS**: Functions that perform dangerous operations if given tainted data (SQL execution, command execution, file operations, deserialization)
- **SANITIZERS**: Functions that clean/validate data to remove taint (input validation, escaping, encoding)

CRITICAL RULES:
1. **NEVER analyze C-extension libraries** (numpy, pandas, scipy, etc.). If you detect a C-extension, set "is_c_extension": true and return empty functions list.
2. Only analyze pure-Python libraries where you can reason about source code behavior.
3. Be conservative - only flag functions you are confident about.
4. Focus on the most security-critical functions (max 20).
5. Provide CWE IDs when applicable (CWE-78 for command injection, CWE-89 for SQL injection, etc.).

Return your analysis as valid JSON matching this schema:
{
  "library_name": "string",
  "ecosystem": "pypi",
  "description": "string (brief library description)",
  "is_c_extension": boolean,
  "confidence": "high|medium|low",
  "functions": [
    {
      "name": "string (fully qualified: module.class.method)",
      "label": "source|sink|sanitizer",
      "description": "string (explain why this is security-relevant)",
      "cwe_id": "string (optional, e.g., CWE-78)",
      "returns_tainted": boolean (for sources, true; for sinks, false)
    }
  ]
}

Return ONLY the JSON object, no additional text."""


def _build_user_prompt(
    library_name: str,
    version: str,
    documentation: Optional[str] = None,
    source_code: Optional[str] = None,
) -> str:
    """
    Build the user prompt for LLM analysis.

    Args:
        library_name: Name of the library to analyze
        version: Library version
        documentation: Optional library documentation
        source_code: Optional source code snippet

    Returns:
        Formatted user prompt
    """
    prompt_parts = [
        f"Analyze the security profile for Python library: **{library_name}** (version {version})"
    ]

    if documentation:
        prompt_parts.append(
            f"\n## Documentation:\n{documentation[:5000]}"
        )  # Limit to 5000 chars

    if source_code:
        prompt_parts.append(
            f"\n## Source Code Sample:\n```python\n{source_code[:3000]}\n```"
        )  # Limit to 3000 chars

    if not documentation and not source_code:
        prompt_parts.append(
            "\nNo documentation or source code provided. Use your knowledge of common Python libraries to infer security-relevant functions."
        )

    prompt_parts.append(
        "\nIdentify the most security-critical functions (sources, sinks, sanitizers) and return the JSON analysis."
    )

    return "\n".join(prompt_parts)


class AIFallbackBuilder:
    """
    LLM-based profile builder for unknown pure-Python libraries.

    This class uses AI to analyze library documentation or source code
    and generate a temporary security profile with inferred labels.
    """

    def __init__(self, ai_client: AIClient, max_functions: int = 20):
        """
        Initialize AI Fallback Builder.

        Args:
            ai_client: AI client for LLM inference
            max_functions: Maximum number of functions to include in profile (default 20)
        """
        self.ai_client = ai_client
        self.max_functions = max_functions

    def analyze_library(
        self,
        library_name: str,
        version: str,
        documentation: Optional[str] = None,
        source_code: Optional[str] = None,
    ) -> Library:
        """
        Analyze a library using LLM and generate a security profile.

        Args:
            library_name: Name of the library
            version: Library version
            documentation: Optional library documentation
            source_code: Optional source code to analyze

        Returns:
            Library profile with AI-inferred security labels

        Raises:
            ValueError: If library_name or version is empty
        """
        if not library_name:
            raise ValueError("library_name cannot be empty")
        if not version:
            raise ValueError("version cannot be empty")

        logger.info(f"Generating AI fallback profile for {library_name} {version}")

        # Build prompts
        system_prompt = SYSTEM_PROMPT
        user_prompt = _build_user_prompt(
            library_name, version, documentation, source_code
        )

        # Call LLM
        try:
            response = self.ai_client.analyze(system_prompt, user_prompt)
            analysis = self._parse_llm_response(response)
        except Exception as e:
            logger.error(f"LLM analysis failed for {library_name}: {e}")
            # Return minimal library on error
            analysis = {
                "library_name": library_name,
                "ecosystem": "pypi",
                "is_c_extension": False,
                "functions": [],
            }

        # Build Library object from analysis
        return self._build_library_from_analysis(library_name, version, analysis)

    def _parse_llm_response(self, response: str) -> dict:
        """
        Parse LLM JSON response.

        Args:
            response: Raw LLM response string

        Returns:
            Parsed analysis dictionary
        """
        # Clean response (remove markdown code blocks if present)
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return {}

    def _build_library_from_analysis(
        self, library_name: str, version: str, analysis: dict
    ) -> Library:
        """
        Build a Library object from LLM analysis.

        Args:
            library_name: Library name
            version: Library version
            analysis: Parsed LLM analysis

        Returns:
            Library profile
        """
        # Extract metadata
        ecosystem = analysis.get("ecosystem", "pypi")
        description = analysis.get("description")
        is_c_extension = analysis.get("is_c_extension", False)

        # Handle C-extension rejection
        if is_c_extension:
            logger.warning(
                f"{library_name} detected as C-extension. AI fallback not supported for binary code."
            )
            description = f"{description or library_name} (C-extension - not supported by AI fallback)"
            functions = []
        else:
            # Parse functions
            functions_data = analysis.get("functions", [])
            functions = self._parse_functions(functions_data)

        # Create library version
        lib_version = LibraryVersion(
            version=version,
            functions=functions,
            release_date=None,
            deprecated=False,
        )

        # Build library
        library = Library(
            name=library_name,
            ecosystem=ecosystem,
            versions=[lib_version],
            description=description,
            homepage=None,
            repository=None,
        )

        return library

    def _parse_functions(self, functions_data: list) -> list[FunctionSpec]:
        """
        Parse function specifications from LLM analysis.

        Args:
            functions_data: List of function dictionaries from LLM

        Returns:
            List of FunctionSpec objects
        """
        functions = []

        # Limit to max_functions
        for func_data in functions_data[: self.max_functions]:
            try:
                # Parse security label
                label_str = func_data.get("label", "none").lower()
                label = SecurityLabel(label_str)

                # Build FunctionSpec
                func = FunctionSpec(
                    name=func_data.get("name", "unknown"),
                    label=label,
                    description=func_data.get("description"),
                    cwe_id=func_data.get("cwe_id"),
                    returns_tainted=func_data.get("returns_tainted", False),
                    parameters=[],  # LLM doesn't provide detailed parameter specs yet
                )

                functions.append(func)
            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to parse function spec: {e}")
                continue

        return functions


# High-level helper function
def generate_shadow_profile(
    library_name: str,
    version: str,
    ai_client: Optional[AIClient] = None,
    documentation: Optional[str] = None,
    source_code: Optional[str] = None,
) -> Library:
    """
    Generate a shadow profile for an unknown library using AI fallback.

    This is the main entry point for AI-based profile generation.

    Args:
        library_name: Name of the library
        version: Library version
        ai_client: AI client for LLM inference (if None, returns minimal library)
        documentation: Optional library documentation
        source_code: Optional source code to analyze

    Returns:
        Library profile with AI-inferred security labels

    Example:
        from src.core.ai.client import LLMClient

        client = LLMClient(provider="openai")
        library = generate_shadow_profile(
            library_name="requests",
            version="2.31.0",
            ai_client=client,
            documentation="Requests is an HTTP library..."
        )
    """
    if ai_client is None:
        logger.warning(
            f"No AI client provided for {library_name}. Returning minimal library profile."
        )
        return Library(
            name=library_name,
            ecosystem="pypi",
            versions=[LibraryVersion(version=version, functions=[])],
        )

    builder = AIFallbackBuilder(ai_client)
    return builder.analyze_library(library_name, version, documentation, source_code)
