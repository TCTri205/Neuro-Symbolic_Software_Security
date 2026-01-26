from packaging.version import parse as parse_version
from packaging.specifiers import SpecifierSet


class VersionMatcher:
    @staticmethod
    def match(version: str, specifier: str) -> bool:
        """
        Checks if a given version string matches a specifier set.

        Args:
            version: The version string to check (e.g., "1.2.3").
            specifier: The specifier string (e.g., ">=1.0.0, <2.0.0").

        Returns:
            True if the version matches the specifier, False otherwise.
        """
        try:
            v = parse_version(version)
            spec = SpecifierSet(specifier)
            return v in spec
        except Exception:
            # If parsing fails, we default to False (safe fail)
            return False

    @staticmethod
    def is_valid(version: str) -> bool:
        try:
            parse_version(version)
            return True
        except Exception:
            return False
