from src.core.privacy.masker import PrivacyMasker


class TestPrivacyMasker:
    def setup_method(self):
        self.masker = PrivacyMasker()

    def test_mask_variables(self):
        code = "secret_key = '12345'\nprint(secret_key)"
        masked, mapping = self.masker.mask(code)

        assert "secret_key" not in masked
        # Expect inferred STR or default VAR (here it's '12345' so likely STR)
        assert "STR_1" in masked or "VAR_1" in masked
        assert "print" in masked  # Builtin preserved
        assert (
            mapping.get("STR_1") == "secret_key" or mapping.get("VAR_1") == "secret_key"
        )

    def test_mask_function(self):
        code = """
def process_data(user_data):
    return user_data * 2
"""
        masked, mapping = self.masker.mask(code)

        assert "process_data" not in masked
        assert "user_data" not in masked
        assert "FUNC_1" in masked
        assert "ARG_1" in masked

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
        assert "CLASS_1" in masked
        assert "__init__" in masked
        assert "__str__" in masked
        assert "self" in masked  # Should be preserved

        # Attribute names (self.val) are NOT masked to prevent breaking external library calls
        # But the argument 'val' used in assignment SHOULD be masked
        assert "self.val" in masked
        # Verify the assignment uses the masked argument
        # Expectation: self.val = ARG_1 (where ARG_1 maps to val)
        assert mapping.get("ARG_1") == "val"
        assert "= ARG_1" in masked

        assert "str" in masked  # builtin call

    def test_consistency(self):
        code = "x = 1; y = x + 1"
        masked, mapping = self.masker.mask(code)

        # x should be masked to same variable both times. x=1 -> INT_1
        assert masked.count("INT_1") == 2
        # y = x + 1. y is assigned a BinOp result.
        # Simple inference sees BinOp -> "VAR". So y -> VAR_1.
        assert "VAR_1" in masked

    def test_syntax_preservation(self):
        code = """
def complex_calc(a, b):
    result = a + b
    return result
"""
        masked, _ = self.masker.mask(code)
        # Compile it to verify syntax validity
        compile(masked, "<string>", "exec")

    def test_typed_masking_args(self):
        code = """
def login(username: str, age: int):
    print(username)
"""
        masked, mapping = self.masker.mask(code)

        # username -> STR_1
        # age -> INT_1
        # login -> FUNC_1 (or func_1 if we keep lowercase, but Doc 05a uses UPPER)

        assert "STR_1" in masked
        assert "INT_1" in masked
        assert mapping["STR_1"] == "username"
        assert mapping["INT_1"] == "age"

    def test_typed_masking_ann_assign(self):
        code = """
count: int = 10
name: str = "Alice"
"""
        masked, mapping = self.masker.mask(code)

        assert "INT_1" in masked
        assert "STR_1" in masked
        assert mapping["INT_1"] == "count"
        assert mapping["STR_1"] == "name"

    def test_inference_from_value(self):
        code = """
x = "hello"
y = 42
z = [1, 2]
"""
        masked, mapping = self.masker.mask(code)

        assert "STR_1" in masked
        assert "INT_1" in masked
        assert "LIST_1" in masked

    def test_taint_aware_masking(self):
        code = """
def query(user_input):
    pass
"""
        # Pass information that 'user_input' is a source/tainted
        masked, mapping = self.masker.mask(code, sensitive_vars={"user_input"})

        # Should be USER_ARG_1 (untyped argument)
        assert "USER_ARG_1" in masked
        assert mapping["USER_ARG_1"] == "user_input"

    def test_taint_and_type(self):
        code = """
def query(user_input: str):
    pass
"""
        masked, mapping = self.masker.mask(code, sensitive_vars={"user_input"})

        assert "USER_STR_1" in masked
        assert mapping["USER_STR_1"] == "user_input"
