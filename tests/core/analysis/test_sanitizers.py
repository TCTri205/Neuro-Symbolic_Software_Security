from src.core.analysis.sanitizers import SanitizerRegistry, SanitizerType


class TestSanitizerRegistry:
    def setup_method(self):
        self.registry = SanitizerRegistry()

    def test_default_mappings(self):
        # Test basic lookups for standard library functions
        assert self.registry.get_sanitizer_type("html.escape") == SanitizerType.HTML
        assert (
            self.registry.get_sanitizer_type("urllib.parse.quote") == SanitizerType.URL
        )
        assert self.registry.get_sanitizer_type("shlex.quote") == SanitizerType.SHELL
        assert (
            self.registry.get_sanitizer_type("os.path.basename") == SanitizerType.PATH
        )

    def test_unknown_function(self):
        # Test lookup for non-sanitizer function
        assert self.registry.get_sanitizer_type("print") is None
        assert self.registry.get_sanitizer_type("my_func") is None

    def test_is_sanitizer(self):
        assert self.registry.is_sanitizer("html.escape") is True
        assert self.registry.is_sanitizer("print") is False

    def test_register_custom_sanitizer(self):
        # Register a new custom sanitizer
        self.registry.register("my.custom.clean", SanitizerType.HTML)

        assert self.registry.is_sanitizer("my.custom.clean") is True
        assert self.registry.get_sanitizer_type("my.custom.clean") == SanitizerType.HTML

    def test_override_sanitizer(self):
        # Allow overriding/updating existing mappings (e.g., if context changes)
        self.registry.register("html.escape", SanitizerType.GENERAL)
        assert self.registry.get_sanitizer_type("html.escape") == SanitizerType.GENERAL
