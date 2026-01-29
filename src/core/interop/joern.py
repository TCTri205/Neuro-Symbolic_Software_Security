"""
Joern Integration Stub

This module provides an interface for integrating Joern (a Code Property Graph analysis tool)
with NSSS. Currently implements a stub/placeholder for future polyglot support.

Joern supports C/C++, Java, PHP, and other languages. Future implementation will:
1. Call joern-parse to generate CPG
2. Export CPG as GraphML/DOT
3. Convert to NSSS IR format

References:
- docs/13_Joern_Integration_Spec.md
- docs/07_IR_Schema.md
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict
from src.core.telemetry import get_logger

logger = get_logger(__name__)


class ExternalParser(ABC):
    """
    Abstract base class for external parser integrations.

    External parsers convert non-Python source code into NSSS IR format,
    enabling polyglot security analysis.
    """

    @abstractmethod
    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a source file and return NSSS IR-compatible dictionary.

        Args:
            file_path: Path to the source file to parse

        Returns:
            Dictionary with keys: 'nodes', 'edges', 'metadata'
            Follows the schema defined in docs/07_IR_Schema.md
        """
        pass

    @abstractmethod
    def check_installed(self) -> bool:
        """
        Check if the external parser tool is installed and available.

        Returns:
            True if the parser is available, False otherwise
        """
        pass


class JoernStub(ExternalParser):
    """
    Stub implementation for Joern integration.

    This is a placeholder that returns empty IR structures. It satisfies
    the ExternalParser interface but does not actually invoke Joern.

    Future implementation will:
    1. Run: joern-parse <file_path>
    2. Run: joern-export --format graphml
    3. Convert GraphML to NSSS IR using mapping:
       - Joern METHOD -> NSSS Function
       - Joern CALL -> NSSS Call
       - Joern IDENTIFIER -> NSSS Variable
       - Joern LITERAL -> NSSS Constant
       - Joern CONTROL_STRUCTURE -> NSSS ControlFlow

    See docs/13_Joern_Integration_Spec.md for complete mapping specification.
    """

    def check_installed(self) -> bool:
        """
        Check if Joern is installed.

        Currently returns False (stub implementation).
        Future implementation will check: subprocess.run(['joern', '--version'])

        Returns:
            False (Joern integration not implemented)
        """
        # TODO: Implement actual check via subprocess
        # Example future implementation:
        # try:
        #     result = subprocess.run(
        #         ['joern', '--version'],
        #         capture_output=True,
        #         text=True,
        #         timeout=5
        #     )
        #     return result.returncode == 0
        # except (FileNotFoundError, subprocess.TimeoutExpired):
        #     return False
        return False

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a source file using Joern (stub implementation).

        Currently returns an empty IR structure. Future implementation will:
        1. Invoke joern-parse to create CPG
        2. Export CPG to GraphML format
        3. Convert GraphML nodes/edges to NSSS IR schema

        Args:
            file_path: Path to source file (e.g., .c, .cpp, .java, .php)

        Returns:
            Dictionary with NSSS IR structure:
            {
                "nodes": [],      # List of IR nodes (empty in stub)
                "edges": [],      # List of IR edges (empty in stub)
                "metadata": {     # Parser metadata
                    "parser": "joern-stub"
                }
            }

        Note:
            Logs a warning indicating this is a stub implementation.
        """
        logger.warning(
            "Joern integration is not yet implemented. Returning empty graph. "
            f"File requested: {file_path}"
        )

        return {"nodes": [], "edges": [], "metadata": {"parser": "joern-stub"}}


def export_stub_ir(file_path: str, output_path: str) -> Dict[str, Any]:
    """
    Run the Joern stub and export IR to disk.

    Args:
        file_path: Source file path to pass to JoernStub
        output_path: JSON file path for exported IR

    Returns:
        The NSSS IR dictionary written to disk
    """
    stub = JoernStub()
    ir = stub.parse_file(file_path)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(ir, indent=2), encoding="utf-8")

    logger.info("Exported Joern stub IR to %s", output_path)
    return ir
