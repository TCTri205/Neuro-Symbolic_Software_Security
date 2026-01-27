import tempfile
from pathlib import Path
from src.core.finetuning.few_shot_registry import FewShotRegistry


def test_add_fix_example():
    """Test adding CVE fix examples (before/after pairs)."""
    registry = FewShotRegistry()

    code_before = "sql = 'SELECT * FROM users WHERE id = %s' % uid"
    code_after = (
        "sql = 'SELECT * FROM users WHERE id = %s'\ncursor.execute(sql, (uid,))"
    )

    registry.add_fix_example(
        code_before=code_before,
        code_after=code_after,
        vuln_type="SQL Injection",
        source="CVEFixes-2024-001",
    )

    examples = registry.get_examples(vuln_type="SQL Injection")
    assert len(examples) == 2  # 1 vulnerable + 1 fixed

    vulnerable = [ex for ex in examples if ex.is_vulnerable]
    fixed = [ex for ex in examples if not ex.is_vulnerable]

    assert len(vulnerable) == 1
    assert len(fixed) == 1
    assert vulnerable[0].code == code_before
    assert fixed[0].code == code_after


def test_add_false_positive():
    """Test storing false positive feedback from triage."""
    registry = FewShotRegistry()

    safe_code = "user_input = request.args.get('name')\nreturn render_template('hello.html', name=escape(user_input))"

    registry.add_false_positive(
        code=safe_code,
        vuln_type="XSS",
        reason="User input is properly escaped before rendering",
        triaged_by="security-analyst",
    )

    examples = registry.get_examples(vuln_type="XSS", example_type="false_positive")
    assert len(examples) == 1
    assert examples[0].code == safe_code
    assert examples[0].is_vulnerable is False
    assert (
        examples[0].metadata["reason"]
        == "User input is properly escaped before rendering"
    )


def test_add_positive_example():
    """Test storing verified vulnerability with reasoning."""
    registry = FewShotRegistry()

    vuln_code = "os.system('tar -xf %s' % user_file)"
    reasoning = (
        "Command injection via string formatting. User can inject shell metacharacters."
    )

    registry.add_positive_example(
        code=vuln_code,
        vuln_type="Command Injection",
        reasoning=reasoning,
        source="Manual Review",
    )

    examples = registry.get_examples(
        vuln_type="Command Injection", example_type="positive"
    )
    assert len(examples) == 1
    assert examples[0].is_vulnerable is True
    assert examples[0].metadata["reasoning"] == reasoning


def test_duplicate_detection():
    """Test that duplicates are detected via content hash."""
    registry = FewShotRegistry()

    code = "eval(user_input)"

    registry.add_positive_example(
        code, "Code Injection", "Uses eval on user input", "Test"
    )
    registry.add_positive_example(
        code, "Code Injection", "Different reasoning", "Test2"
    )

    examples = registry.get_examples(vuln_type="Code Injection")
    assert len(examples) == 1  # Duplicate should be ignored


def test_get_examples_by_type():
    """Test filtering examples by vulnerability type."""
    registry = FewShotRegistry()

    registry.add_positive_example(
        "sql = 'SELECT * FROM users WHERE id = ' + uid",
        "SQL Injection",
        "String concat",
        "Test",
    )
    registry.add_positive_example(
        "os.system(user_cmd)", "Command Injection", "Direct execution", "Test"
    )
    registry.add_positive_example("eval(data)", "Code Injection", "Eval usage", "Test")

    sql_examples = registry.get_examples(vuln_type="SQL Injection")
    assert len(sql_examples) == 1
    assert sql_examples[0].vuln_type == "SQL Injection"

    all_examples = registry.get_examples()
    assert len(all_examples) == 3


def test_persistence():
    """Test saving and loading registry to/from disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "registry.json"

        # Create and populate registry
        registry1 = FewShotRegistry(storage_path=registry_path)
        registry1.add_positive_example(
            code="pickle.loads(user_data)",
            vuln_type="Deserialization",
            reasoning="Unsafe pickle usage",
            source="Test",
        )
        registry1.save()

        # Load into new instance
        registry2 = FewShotRegistry(storage_path=registry_path)
        registry2.load()

        examples = registry2.get_examples(vuln_type="Deserialization")
        assert len(examples) == 1
        assert examples[0].code == "pickle.loads(user_data)"


def test_to_training_format():
    """Test conversion to training dataset format (for LLM fine-tuning)."""
    registry = FewShotRegistry()

    registry.add_fix_example(
        code_before="sql = f'SELECT * FROM users WHERE name = {user_name}'",
        code_after="sql = 'SELECT * FROM users WHERE name = %s'\ncursor.execute(sql, (user_name,))",
        vuln_type="SQL Injection",
        source="CVE-2024-001",
    )

    training_data = registry.to_training_format(vuln_type="SQL Injection")

    assert len(training_data) == 2  # Vulnerable + Fixed

    # Check vulnerable example
    vuln_example = [ex for ex in training_data if ex["output"]["is_vulnerable"]][0]
    assert "f'SELECT" in vuln_example["input"]["function_signature"]
    assert vuln_example["output"]["is_vulnerable"] is True

    # Check fixed example
    fixed_example = [ex for ex in training_data if not ex["output"]["is_vulnerable"]][0]
    assert (
        "cursor.execute(sql, (user_name,))"
        in fixed_example["input"]["function_signature"]
    )
    assert fixed_example["output"]["is_vulnerable"] is False
