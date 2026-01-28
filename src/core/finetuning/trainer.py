import json
from src.core.telemetry import get_logger

logger = get_logger(__name__)

try:
    from unsloth import FastLanguageModel, is_bfloat16_supported
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from datasets import load_dataset
except ImportError:
    FastLanguageModel = None
    SFTTrainer = None
    TrainingArguments = None
    load_dataset = None

    def is_bfloat16_supported():
        return False

    logger.warning("Unsloth/TRL not installed. Training will fail if attempted.")


class Finetuner:
    def __init__(self, model_name: str = "Qwen/Qwen2.5-Coder-7B-Instruct"):
        self.model_name = model_name

    def train(self, dataset_path: str, output_dir: str):
        if not FastLanguageModel:
            raise ImportError("Unsloth is required for training.")

        # 1. Load Model
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=self.model_name,
            max_seq_length=4096,
            dtype=None,
            load_in_4bit=True,
        )

        # 2. Add LoRA adapters
        model = FastLanguageModel.get_peft_model(
            model,
            r=16,
            target_modules=[
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ],
            lora_alpha=16,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
        )

        # 3. Load Dataset
        dataset = load_dataset("json", data_files=dataset_path, split="train")

        # 4. Train
        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            dataset_text_field="text",
            max_seq_length=4096,
            dataset_kwargs={
                "add_special_tokens": False,  # We template manually
            },
            formatting_func=self._formatting_prompts_func,
            args=TrainingArguments(
                per_device_train_batch_size=2,
                gradient_accumulation_steps=4,
                warmup_steps=5,
                max_steps=60,  # Demo/POC
                learning_rate=2e-4,
                fp16=not is_bfloat16_supported(),
                bf16=is_bfloat16_supported(),
                logging_steps=1,
                optim="adamw_8bit",
                output_dir=output_dir,
            ),
        )
        trainer.train()

        # Save
        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)

    def _formatting_prompts_func(self, examples):
        # Support both formats: legacy "input_data"/"output_data" and new "input"/"output"
        instructions = examples.get("instruction", [])
        inputs = examples.get("input", examples.get("input_data", []))
        outputs = examples.get("output", examples.get("output_data", []))

        texts = []
        for instruction, input_obj, output in zip(instructions, inputs, outputs):
            # Convert input to string (may be dict or string)
            if isinstance(input_obj, dict):
                input_str = json.dumps(input_obj, indent=2)
            else:
                input_str = str(input_obj)

            # Convert output to string (may be dict or string)
            if isinstance(output, dict):
                output_str = json.dumps(output, indent=2)
            else:
                output_str = str(output)

            # Simple format (Alpaca-style or ChatML-style)
            # Using basic Instruction/Input/Response for now
            text = (
                f"### Instruction:\n{instruction}\n\n"
                f"### Input:\n{input_str}\n\n"
                f"### Response:\n{output_str}"
            )
            texts.append(text)
        return texts
