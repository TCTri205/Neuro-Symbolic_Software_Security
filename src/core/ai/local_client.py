import logging
import os
from pathlib import Path

from src.core.ai.client import AIClient
from src.core.finetuning.inference import InferenceEngine

logger = logging.getLogger(__name__)


class LocalLLMClient(AIClient):
    """
    AI Client that uses a locally loaded model (via Unsloth) for inference.
    Supports automatic fallback to Base Model if fine-tuned model is missing.
    """

    def __init__(self, model: str = None):
        # 1. Determine model path priority:
        #    a) Constructor arg (if provided)
        #    b) Env var 'LOCAL_MODEL_PATH'
        #    c) Default fine-tuned path 'outputs/qwen-security-model'
        #    d) Fallback to Base Model 'Qwen/Qwen2.5-Coder-7B-Instruct'

        default_ft_path = "outputs/qwen-security-model"
        base_model_name = "Qwen/Qwen2.5-Coder-7B-Instruct"

        if model:
            target_path = model
        else:
            target_path = os.getenv("LOCAL_MODEL_PATH", default_ft_path)

        # 2. Check existence. If FT path doesn't exist, use Base Model.
        if target_path == default_ft_path and not os.path.exists(target_path):
            logger.warning(
                f"⚠️ Fine-tuned model not found at '{target_path}'. "
                f"Falling back to Base Model: '{base_model_name}'"
            )
            target_path = base_model_name

        logger.info(f"🤖 LocalLLMClient initialized with model: {target_path}")
        self.engine = InferenceEngine(target_path)
        self.initialized = False

    def load_model(self):
        """Explicitly load the model. Can be called at startup."""
        if not self.initialized:
            self.engine.load()
            self.initialized = True

    def analyze(self, system_prompt: str, user_prompt: str) -> str:
        """
        Analyze using the local model.

        Args:
            system_prompt: The instruction (e.g., "Analyze the following...")
            user_prompt: The input data (JSON string or code)

        Returns:
            The raw text response from the model.
        """
        if not self.initialized:
            # Lazy load if not already loaded
            self.load_model()

        # Format the prompt according to the training template
        # Training format:
        # ### Instruction:
        # {instruction}
        #
        # ### Input:
        # {input_str}
        #
        # ### Response:

        full_prompt = (
            f"### Instruction:\n{system_prompt}\n\n"
            f"### Input:\n{user_prompt}\n\n"
            f"### Response:\n"
        )

        response = self.engine.generate(full_prompt)
        return response
