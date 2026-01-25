from enum import Enum, auto
from typing import Dict, Optional


class SanitizerType(Enum):
    HTML = auto()  # Prevents XSS
    URL = auto()  # Prevents Injection in URLs
    SHELL = auto()  # Prevents Command Injection
    SQL = auto()  # Prevents SQL Injection
    PATH = auto()  # Prevents Path Traversal
    GENERAL = auto()  # General purpose encoding/cleaning


class SanitizerRegistry:
    """
    Registry to map function names to their sanitization capabilities.
    """

    # Pre-defined mapping of common python library functions to sanitizer types
    _DEFAULT_MAPPING: Dict[str, SanitizerType] = {
        # HTML / XSS
        "html.escape": SanitizerType.HTML,
        "cgi.escape": SanitizerType.HTML,  # Legacy
        "markupsafe.escape": SanitizerType.HTML,
        # URL
        "urllib.parse.quote": SanitizerType.URL,
        "urllib.parse.quote_plus": SanitizerType.URL,
        # Shell / Command Injection
        "shlex.quote": SanitizerType.SHELL,
        "pipes.quote": SanitizerType.SHELL,  # Legacy
        # Path
        "os.path.basename": SanitizerType.PATH,
        "ntpath.basename": SanitizerType.PATH,
        "posixpath.basename": SanitizerType.PATH,
        # General
        "base64.b64encode": SanitizerType.GENERAL,
    }

    def __init__(self):
        self._registry: Dict[str, SanitizerType] = self._DEFAULT_MAPPING.copy()

    def register(self, func_name: str, sanitizer_type: SanitizerType) -> None:
        """Register a custom sanitizer function."""
        self._registry[func_name] = sanitizer_type

    def get_sanitizer_type(self, func_name: str) -> Optional[SanitizerType]:
        """
        Get the SanitizerType for a given function name.
        Returns None if the function is not a known sanitizer.
        """
        return self._registry.get(func_name)

    def is_sanitizer(self, func_name: str) -> bool:
        """Check if a function is a registered sanitizer."""
        return func_name in self._registry
