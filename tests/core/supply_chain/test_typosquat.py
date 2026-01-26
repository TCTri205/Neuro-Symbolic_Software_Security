import pytest
from src.core.supply_chain.typosquat import TyposquatScanner


class TestTyposquatScanner:
    @pytest.fixture
    def scanner(self):
        return TyposquatScanner()

    def test_levenshtein_distance(self, scanner):
        assert scanner._levenshtein_distance("kitten", "sitting") == 3
        assert scanner._levenshtein_distance("flaw", "lawn") == 2
        assert scanner._levenshtein_distance("requests", "requests") == 0
        assert scanner._levenshtein_distance("requests", "rquests") == 1

    def test_check_package_exact_match(self, scanner):
        # Should return empty list for known popular packages
        assert scanner.check_package("requests") == []
        assert scanner.check_package("flask") == []

    def test_check_package_typosquat(self, scanner):
        # rquests is distance 1 from requests
        assert "requests" in scanner.check_package("rquests")

        # djang is distance 1 from django
        assert "django" in scanner.check_package("djang")

        # numpyy is distance 1 from numpy
        assert "numpy" in scanner.check_package("numpyy")

    def test_check_package_safe_unknown(self, scanner):
        # A completely different package
        assert scanner.check_package("my-custom-utils") == []

    def test_parse_requirements(self, scanner):
        content = """
        requests==2.0.0
        flask>=1.0
        # This is a comment
        django
        numpy~=1.2.0
        """
        packages = scanner.parse_requirements_file(content)
        assert "requests" in packages
        assert "flask" in packages
        assert "django" in packages
        assert "numpy" in packages
        assert len(packages) == 4

    def test_scan_integration(self, scanner):
        content = """
        rquests==2.0.0
        flask
        panda
        """
        results = scanner.scan(content)

        # Should detect rquests and panda (typos of requests and pandas)
        detected_pkgs = {r["package"] for r in results}
        assert "rquests" in detected_pkgs
        assert "panda" in detected_pkgs
        assert "flask" not in detected_pkgs

        # Verify details for rquests
        rquests_result = next(r for r in results if r["package"] == "rquests")
        assert "requests" in rquests_result["candidates"]
        assert rquests_result["risk"] == "HIGH"
