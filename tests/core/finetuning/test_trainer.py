from unittest.mock import MagicMock, patch
import sys

# Mock unsloth and trl modules
sys.modules["unsloth"] = MagicMock()
sys.modules["trl"] = MagicMock()
sys.modules["transformers"] = MagicMock()
sys.modules["peft"] = MagicMock()
sys.modules["datasets"] = MagicMock()

from src.core.finetuning.trainer import Finetuner  # noqa: E402


@patch("src.core.finetuning.trainer.FastLanguageModel")
@patch("src.core.finetuning.trainer.SFTTrainer")
def test_finetuner_train_flow(mock_trainer_cls, mock_flm):
    # Setup mocks
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()
    mock_flm.from_pretrained.return_value = (mock_model, mock_tokenizer)
    # Ensure get_peft_model returns the model (or a wrapper)
    mock_flm.get_peft_model.return_value = mock_model

    finetuner = Finetuner(model_name="Qwen/Qwen2.5-Coder-7B-Instruct")

    # Execute
    finetuner.train(
        dataset_path="tests/fixtures/dummy_dataset.jsonl", output_dir="outputs/test_run"
    )

    # Verify Model Loading
    mock_flm.from_pretrained.assert_called_once()

    # Verify LoRA application
    mock_flm.get_peft_model.assert_called_once()

    # Verify Trainer Initialization
    mock_trainer_cls.assert_called_once()
    call_args = mock_trainer_cls.call_args
    assert call_args.kwargs["model"] == mock_model
    assert call_args.kwargs["tokenizer"] == mock_tokenizer

    # Verify Training
    mock_trainer_cls.return_value.train.assert_called_once()
