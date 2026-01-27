"""
Tests for AI Fallback Profile Builder

Tests the LLM-based profile generation for unknown pure-Python libraries.
"""

import json
import pytest
from unittest.mock import Mock, patch

from src.librarian.ai_fallback import AIFallbackBuilder, generate_shadow_profile
from src.librarian.models import SecurityLabel
from src.core.ai.client import MockAIClient


class TestAIFallbackBuilder:
    """Test AIFallbackBuilder LLM-based profile generation."""

    def test_basic_creation(self):
        """Test creating an AI fallback builder."""
        client = MockAIClient()
        builder = AIFallbackBuilder(client)

        assert builder.ai_client is not None
        assert builder.max_functions == 20  # Default limit

    def test_custom_max_functions(self):
        """Test setting custom max functions limit."""
        client = MockAIClient()
        builder = AIFallbackBuilder(client, max_functions=50)

        assert builder.max_functions == 50

    def test_analyze_library_with_mock_llm(self):
        """Test analyzing a library with mock LLM."""
        client = MockAIClient()
        builder = AIFallbackBuilder(client)

        # This should not crash even though mock returns non-JSON
        library = builder.analyze_library(
            library_name="cryptography",
            version="41.0.0",
            source_code=None,
            documentation="A Python library for cryptographic operations.",
        )

        # With mock client, we should get a minimal library profile
        assert library is not None
        assert library.name == "cryptography"
        assert library.ecosystem == "pypi"

    @patch("src.core.ai.client.LLMClient")
    def test_analyze_library_with_valid_llm_response(self, mock_llm_class):
        """Test analyzing a library with a valid LLM JSON response."""
        # Setup mock LLM to return valid JSON
        mock_client = Mock()
        mock_llm_class.return_value = mock_client

        llm_response = json.dumps(
            {
                "library_name": "cryptography",
                "ecosystem": "pypi",
                "description": "Cryptographic library for Python",
                "is_c_extension": False,
                "confidence": "high",
                "functions": [
                    {
                        "name": "cryptography.fernet.Fernet.decrypt",
                        "label": "sink",
                        "description": "Decryption sink (sensitive data)",
                        "cwe_id": "CWE-327",
                        "returns_tainted": False,
                    },
                    {
                        "name": "cryptography.hazmat.primitives.serialization.load_pem_private_key",
                        "label": "source",
                        "description": "Loads private key from file",
                        "cwe_id": "CWE-798",
                        "returns_tainted": True,
                    },
                ],
            }
        )

        mock_client.analyze.return_value = llm_response

        builder = AIFallbackBuilder(mock_client)
        library = builder.analyze_library(
            library_name="cryptography",
            version="41.0.0",
            documentation="Cryptographic library",
        )

        assert library.name == "cryptography"
        assert library.ecosystem == "pypi"
        assert library.description == "Cryptographic library for Python"
        assert len(library.versions) == 1
        assert library.versions[0].version == "41.0.0"
        assert len(library.versions[0].functions) == 2

        # Check first function (sink)
        sink = library.versions[0].functions[0]
        assert sink.name == "cryptography.fernet.Fernet.decrypt"
        assert sink.label == SecurityLabel.SINK
        assert sink.cwe_id == "CWE-327"

        # Check second function (source)
        source = library.versions[0].functions[1]
        assert (
            source.name
            == "cryptography.hazmat.primitives.serialization.load_pem_private_key"
        )
        assert source.label == SecurityLabel.SOURCE
        assert source.returns_tainted is True

    @patch("src.core.ai.client.LLMClient")
    def test_c_extension_detection(self, mock_llm_class):
        """Test that C-extension libraries are rejected."""
        mock_client = Mock()
        mock_llm_class.return_value = mock_client

        llm_response = json.dumps(
            {
                "library_name": "numpy",
                "ecosystem": "pypi",
                "description": "Numerical computing library",
                "is_c_extension": True,  # C-extension detected
                "confidence": "high",
                "functions": [],
            }
        )

        mock_client.analyze.return_value = llm_response

        builder = AIFallbackBuilder(mock_client)
        library = builder.analyze_library(
            library_name="numpy", version="1.26.0", documentation="NumPy library"
        )

        # Should return minimal profile with warning
        assert library.name == "numpy"
        assert library.description is not None
        assert (
            "C-extension" in library.description
            or "not supported" in library.description
        )

    @patch("src.core.ai.client.LLMClient")
    def test_max_functions_limit(self, mock_llm_class):
        """Test that max_functions limit is enforced."""
        mock_client = Mock()
        mock_llm_class.return_value = mock_client

        # Create response with 30 functions
        functions = [
            {
                "name": f"lib.func_{i}",
                "label": "sink",
                "description": f"Function {i}",
            }
            for i in range(30)
        ]

        llm_response = json.dumps(
            {
                "library_name": "testlib",
                "ecosystem": "pypi",
                "is_c_extension": False,
                "functions": functions,
            }
        )

        mock_client.analyze.return_value = llm_response

        # Set limit to 10
        builder = AIFallbackBuilder(mock_client, max_functions=10)
        library = builder.analyze_library(
            library_name="testlib", version="1.0.0", documentation="Test library"
        )

        # Should only include 10 functions
        assert len(library.versions[0].functions) <= 10

    def test_invalid_json_response(self):
        """Test handling of invalid JSON from LLM."""
        client = Mock()
        client.analyze.return_value = "This is not JSON at all!"

        builder = AIFallbackBuilder(client)
        library = builder.analyze_library(
            library_name="badlib", version="1.0.0", documentation="Test"
        )

        # Should return minimal valid library
        assert library.name == "badlib"
        assert len(library.versions) == 1
        assert len(library.versions[0].functions) == 0

    @patch("src.core.ai.client.LLMClient")
    def test_partial_json_response(self, mock_llm_class):
        """Test handling of incomplete JSON response."""
        mock_client = Mock()
        mock_llm_class.return_value = mock_client

        # Missing required fields
        llm_response = json.dumps({"library_name": "partiallib"})

        mock_client.analyze.return_value = llm_response

        builder = AIFallbackBuilder(mock_client)
        library = builder.analyze_library(library_name="partiallib", version="1.0.0")

        # Should fill in defaults
        assert library.name == "partiallib"
        assert library.ecosystem == "pypi"  # Default

    @patch("src.core.ai.client.LLMClient")
    def test_sanitizer_function_parsing(self, mock_llm_class):
        """Test parsing sanitizer functions from LLM response."""
        mock_client = Mock()
        mock_llm_class.return_value = mock_client

        llm_response = json.dumps(
            {
                "library_name": "sanitize",
                "ecosystem": "pypi",
                "is_c_extension": False,
                "functions": [
                    {
                        "name": "sanitize.clean_sql",
                        "label": "sanitizer",
                        "description": "Sanitizes SQL input",
                    }
                ],
            }
        )

        mock_client.analyze.return_value = llm_response

        builder = AIFallbackBuilder(mock_client)
        library = builder.analyze_library(library_name="sanitize", version="1.0.0")

        sanitizer = library.versions[0].functions[0]
        assert sanitizer.label == SecurityLabel.SANITIZER
        assert "sql" in sanitizer.name.lower()


class TestGenerateShadowProfile:
    """Test the high-level generate_shadow_profile helper function."""

    @patch("src.core.ai.client.LLMClient")
    def test_generate_shadow_profile_basic(self, mock_llm_class):
        """Test basic shadow profile generation."""
        mock_client = Mock()
        mock_llm_class.return_value = mock_client

        llm_response = json.dumps(
            {
                "library_name": "requests",
                "ecosystem": "pypi",
                "is_c_extension": False,
                "functions": [
                    {
                        "name": "requests.get",
                        "label": "sink",
                        "description": "HTTP GET request (SSRF risk)",
                        "cwe_id": "CWE-918",
                    }
                ],
            }
        )

        mock_client.analyze.return_value = llm_response

        library = generate_shadow_profile(
            library_name="requests",
            version="2.31.0",
            ai_client=mock_client,
            documentation="Requests is an HTTP library for Python.",
        )

        assert library.name == "requests"
        assert len(library.versions) == 1
        assert library.versions[0].version == "2.31.0"
        assert len(library.versions[0].functions) == 1

    def test_generate_shadow_profile_with_source_code(self):
        """Test shadow profile generation with source code."""
        client = Mock()
        client.analyze.return_value = json.dumps(
            {
                "library_name": "customlib",
                "is_c_extension": False,
                "functions": [],
            }
        )

        library = generate_shadow_profile(
            library_name="customlib",
            version="1.0.0",
            ai_client=client,
            source_code="def dangerous_eval(code): return eval(code)",
        )

        assert library.name == "customlib"
        # Should have called analyze with source code in prompt
        assert client.analyze.called

    def test_generate_shadow_profile_without_ai_client(self):
        """Test shadow profile generation fallback when no AI client provided."""
        library = generate_shadow_profile(
            library_name="noai", version="1.0.0", ai_client=None
        )

        # Should return minimal library without crashing
        assert library.name == "noai"
        assert len(library.versions) == 1
        assert len(library.versions[0].functions) == 0


class TestPromptGeneration:
    """Test the prompt generation logic."""

    @patch("src.core.ai.client.LLMClient")
    def test_prompt_includes_library_name(self, mock_llm_class):
        """Test that prompt includes library name."""
        mock_client = Mock()
        mock_llm_class.return_value = mock_client
        mock_client.analyze.return_value = "{}"

        builder = AIFallbackBuilder(mock_client)
        builder.analyze_library(library_name="testlib", version="1.0.0")

        # Check that analyze was called
        assert mock_client.analyze.called
        call_args = mock_client.analyze.call_args

        # User prompt should contain library name
        user_prompt = call_args[0][1]

        assert "testlib" in user_prompt

    @patch("src.core.ai.client.LLMClient")
    def test_prompt_includes_documentation(self, mock_llm_class):
        """Test that prompt includes provided documentation."""
        mock_client = Mock()
        mock_llm_class.return_value = mock_client
        mock_client.analyze.return_value = "{}"

        builder = AIFallbackBuilder(mock_client)
        builder.analyze_library(
            library_name="testlib",
            version="1.0.0",
            documentation="This is the documentation for testlib.",
        )

        call_args = mock_client.analyze.call_args
        user_prompt = call_args[0][1]

        assert "This is the documentation for testlib" in user_prompt

    @patch("src.core.ai.client.LLMClient")
    def test_prompt_includes_source_code(self, mock_llm_class):
        """Test that prompt includes source code when provided."""
        mock_client = Mock()
        mock_llm_class.return_value = mock_client
        mock_client.analyze.return_value = "{}"

        source = "def func(): pass"
        builder = AIFallbackBuilder(mock_client)
        builder.analyze_library(
            library_name="testlib", version="1.0.0", source_code=source
        )

        call_args = mock_client.analyze.call_args
        user_prompt = call_args[0][1]

        assert "def func(): pass" in user_prompt


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_library_name(self):
        """Test handling of empty library name."""
        client = Mock()
        builder = AIFallbackBuilder(client)

        with pytest.raises(ValueError, match="library_name"):
            builder.analyze_library(library_name="", version="1.0.0")

    def test_empty_version(self):
        """Test handling of empty version."""
        client = Mock()
        builder = AIFallbackBuilder(client)

        with pytest.raises(ValueError, match="version"):
            builder.analyze_library(library_name="testlib", version="")

    def test_no_documentation_or_source(self):
        """Test analysis with neither documentation nor source code."""
        client = Mock()
        client.analyze.return_value = json.dumps(
            {"library_name": "minimal", "is_c_extension": False, "functions": []}
        )

        builder = AIFallbackBuilder(client)
        library = builder.analyze_library(
            library_name="minimal",
            version="1.0.0",
            documentation=None,
            source_code=None,
        )

        # Should still work, but prompt will be minimal
        assert library.name == "minimal"

    @patch("src.core.ai.client.LLMClient")
    def test_llm_timeout_handling(self, mock_llm_class):
        """Test handling of LLM timeout."""
        mock_client = Mock()
        mock_llm_class.return_value = mock_client
        mock_client.analyze.side_effect = TimeoutError("LLM timeout")

        builder = AIFallbackBuilder(mock_client)
        library = builder.analyze_library(library_name="timeout_test", version="1.0.0")

        # Should return minimal library on timeout
        assert library.name == "timeout_test"
        assert len(library.versions[0].functions) == 0

    @patch("src.core.ai.client.LLMClient")
    def test_llm_api_error_handling(self, mock_llm_class):
        """Test handling of LLM API errors."""
        mock_client = Mock()
        mock_llm_class.return_value = mock_client
        mock_client.analyze.side_effect = RuntimeError("API error")

        builder = AIFallbackBuilder(mock_client)
        library = builder.analyze_library(library_name="error_test", version="1.0.0")

        # Should return minimal library on error
        assert library.name == "error_test"
        assert len(library.versions[0].functions) == 0
