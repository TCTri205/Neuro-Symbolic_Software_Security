import unittest
from src.librarian.version import VersionMatcher

class TestVersionMatcher(unittest.TestCase):
    def test_basic_match(self):
        self.assertTrue(VersionMatcher.match("2.0.1", "==2.0.1"))
        self.assertTrue(VersionMatcher.match("2.0.1", ">=2.0.0"))
        self.assertTrue(VersionMatcher.match("2.0.1", "<3.0.0"))
        self.assertFalse(VersionMatcher.match("1.0.0", ">2.0.0"))

    def test_complex_specifiers(self):
        spec = ">=1.5, <2.0, !=1.5.1"
        self.assertTrue(VersionMatcher.match("1.5.0", spec))
        self.assertTrue(VersionMatcher.match("1.9.9", spec))
        self.assertFalse(VersionMatcher.match("1.5.1", spec))
        self.assertFalse(VersionMatcher.match("2.0.0", spec))

    def test_invalid_versions(self):
        # Should gracefully handle invalid inputs
        self.assertFalse(VersionMatcher.match("invalid", ">=1.0"))
        self.assertFalse(VersionMatcher.match("1.0", "invalid_spec"))

    def test_is_valid(self):
        self.assertTrue(VersionMatcher.is_valid("1.0.0"))
        self.assertTrue(VersionMatcher.is_valid("1.0"))
        self.assertFalse(VersionMatcher.is_valid("not_a_version"))

if __name__ == "__main__":
    unittest.main()
