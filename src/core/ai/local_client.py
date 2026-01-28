import logging

from src.core.ai.client import AIClient
from src.core.finetuning.inference import InferenceEngine

logger = logging.getLogger(__name__)


class LocalLLMClient(AIClient):
    """
    AI Client that uses a locally loaded model (via Unsloth) for inference.
    """

    def __init__(self, model_path: str = "outputs/qwen-security-model"):
        self.engine = InferenceEngine(model_path)
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
