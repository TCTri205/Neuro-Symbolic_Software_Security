"""
Integration test for training workflow with FewShotRegistry.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock heavy dependencies before importing (must be before src imports)
sys.modules["unsloth"] = MagicMock()
sys.modules["trl"] = MagicMock()
sys.modules["transformers"] = MagicMock()
sys.modules["peft"] = MagicMock()
sys.modules["datasets"] = MagicMock()

from src.core.finetuning.few_shot_registry import FewShotRegistry  # noqa: E402
from src.core.finetuning.trainer import Finetuner  # noqa: E402


def test_trainer_can_load_dataset_from_registry():
    """Test that Finetuner can consume training examples from FewShotRegistry."""
    # Create registry with examples
    registry = FewShotRegistry()
    registry.add_positive_example(
        code="def unsafe(u):\n    eval(u)",
        vuln_type="Code Injection",
        reasoning="Direct eval() usage allows arbitrary code execution.",
        source="Manual Review",
    )
    registry.add_false_positive(
        code="def safe(u):\n    import ast\n    ast.literal_eval(u)",
        vuln_type="Code Injection",
        reason="ast.literal_eval is safe for literals.",
        triaged_by="Security Analyst",
    )

    # Convert to training format
    training_data = registry.to_training_format()

    # Should produce at least 2 training examples
    assert len(training_data) >= 2

    # Check structure (registry uses "input" and "output", not "input_data")
    assert "instruction" in training_data[0]
    assert "input" in training_data[0]
    assert "output" in training_data[0]

    # Verify vulnerable example
    vuln_example = training_data[0]
    output = vuln_example["output"]
    assert output["is_vulnerable"] is True
    assert (
        "eval()" in output["analysis_summary"]
        or "Direct eval" in output["analysis_summary"]
    )


def test_trainer_export_to_jsonl():
    """Test exporting FewShotRegistry examples to JSONL for Finetuner."""
    registry = FewShotRegistry()
    registry.add_fix_example(
        code_before="query = f'SELECT * FROM users WHERE id={uid}'",
        code_after="query = 'SELECT * FROM users WHERE id=%s'\ncursor.execute(query, (uid,))",
        vuln_type="SQL Injection",
        source="CVEFixes-2024-001",
    )

    training_data = registry.to_training_format()

    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_path = Path(tmpdir) / "train_dataset.jsonl"

        # Write to JSONL
        with open(dataset_path, "w", encoding="utf-8") as f:
            for example in training_data:
                f.write(json.dumps(example) + "\n")

        # Verify file created
        assert dataset_path.exists()
        assert dataset_path.stat().st_size > 0

        # Read back
        with open(dataset_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == len(training_data)

            # Parse first line
            first = json.loads(lines[0])
            assert "instruction" in first
            assert "input" in first  # Registry uses "input", not "input_data"


@patch("src.core.finetuning.trainer.FastLanguageModel")
@patch("src.core.finetuning.trainer.SFTTrainer")
@patch("src.core.finetuning.trainer.load_dataset")
def test_trainer_train_from_registry_jsonl(
    mock_load_dataset, mock_sft_trainer_cls, mock_flm
):
    """Test full training flow: Registry -> JSONL -> Finetuner.train()."""
    # Setup mocks
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()
    mock_flm.from_pretrained.return_value = (mock_model, mock_tokenizer)
    mock_flm.get_peft_model.return_value = mock_model
    mock_load_dataset.return_value = MagicMock()  # Mock HF dataset

    # Create registry
    registry = FewShotRegistry()
    registry.add_positive_example(
        code="def unsafe(sql_input):\n    cursor.execute(sql_input)",
        vuln_type="SQL Injection",
        reasoning="Direct execution of user input.",
        source="Manual Review",
    )

    training_data = registry.to_training_format()

    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_path = Path(tmpdir) / "train.jsonl"
        output_dir = Path(tmpdir) / "model_output"

        # Write dataset
        with open(dataset_path, "w", encoding="utf-8") as f:
            for example in training_data:
                f.write(json.dumps(example) + "\n")

        # Train
        finetuner = Finetuner(model_name="Qwen/Qwen2.5-Coder-7B-Instruct")
        finetuner.train(dataset_path=str(dataset_path), output_dir=str(output_dir))

        # Verify training was triggered
        mock_flm.from_pretrained.assert_called_once()
        mock_flm.get_peft_model.assert_called_once()
        mock_sft_trainer_cls.assert_called_once()
        mock_sft_trainer_cls.return_value.train.assert_called_once()


def test_registry_has_sufficient_examples_for_training():
    """Test that registry can accumulate enough examples for meaningful training."""
    registry = FewShotRegistry()

    # Simulate adding multiple examples (minimum ~50 for POC)
    vuln_types = ["SQL Injection", "XSS", "Code Injection", "Path Traversal"]

    for i in range(20):
        vuln_type = vuln_types[i % len(vuln_types)]
        registry.add_positive_example(
            code=f"def vuln_{i}(user_input):\n    dangerous_func(user_input)",
            vuln_type=vuln_type,
            reasoning=f"Example {i}",
            source="Synthetic",
        )
        registry.add_false_positive(
            code=f"def safe_{i}(user_input):\n    sanitized = sanitize(user_input)\n    safe_func(sanitized)",
            vuln_type=vuln_type,
            reason=f"Sanitized at {i}",
            triaged_by="Test Harness",
        )

    training_data = registry.to_training_format()

    # Should have at least 40 examples (20 positive + 20 false positives)
    assert len(training_data) >= 40

    # Check diversity
    vuln_types_in_data = set()
    for ex in training_data:
        # Extract vuln_type from input dict
        input_obj = ex["input"]
        vuln_types_in_data.add(input_obj["vulnerability_type"])

    assert len(vuln_types_in_data) >= 3  # At least 3 different types
