from src.core.privacy.masker import PrivacyMasker


class TestPrivacyMasker:
    def setup_method(self):
        self.masker = PrivacyMasker()

    def test_mask_variables(self):
        code = "secret_key = '12345'\nprint(secret_key)"
        masked, mapping = self.masker.mask(code)

        assert "secret_key" not in masked
        assert "var_1" in masked or "var_2" in masked
        assert "print" in masked  # Builtin preserved
        assert mapping["var_1"] == "secret_key"

    def test_mask_function(self):
        code = """
def process_data(user_data):
    return user_data * 2
"""
        masked, mapping = self.masker.mask(code)

        assert "process_data" not in masked
        assert "user_data" not in masked
        assert "func_1" in masked
        assert "arg_1" in masked

    def test_preserve_builtins_and_magic(self):
        code = """
class MyClass:
    def __init__(self, val):
        self.val = val
        
    def __str__(self):
        return str(self.val)
"""
        masked, mapping = self.masker.mask(code)

        assert "MyClass" not in masked
        assert "class_1" in masked
        assert "__init__" in masked
        assert "__str__" in masked
        assert "self" in masked  # Should be preserved

        # Attribute names (self.val) are NOT masked to prevent breaking external library calls
        # But the argument 'val' used in assignment SHOULD be masked
        assert "self.val" in masked
        # Verify the assignment uses the masked argument
        # Expectation: self.val = arg_1 (where arg_1 maps to val)
        assert mapping.get("arg_1") == "val"
        assert "= arg_1" in masked

        assert "str" in masked  # builtin call

    def test_consistency(self):
        code = "x = 1; y = x + 1"
        masked, mapping = self.masker.mask(code)

        # x should be masked to same variable both times
        assert masked.count("var_1") == 2
        assert "var_2" in masked  # y

    def test_syntax_preservation(self):
        code = """
def complex_calc(a, b):
    result = a + b
    return result
"""
        masked, _ = self.masker.mask(code)
        # Compile it to verify syntax validity
        compile(masked, "<string>", "exec")
