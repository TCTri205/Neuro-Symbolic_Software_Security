import logging
import torch

# Configure logger
logger = logging.getLogger(__name__)

# Try importing Unsloth, but allow running without it (for laptop side testing)
try:
    from unsloth import FastLanguageModel
except ImportError:
    FastLanguageModel = None
    logger.warning("Unsloth not installed. InferenceEngine will not work.")


class InferenceEngine:
    """
    Engine for running inference on Fine-tuned models using Unsloth.
    Designed to run in the Colab environment.
    """

    def __init__(self, model_path: str = "outputs/qwen-security-model"):
        self.model_path = model_path
        self.model = None
        self.tokenizer = None

    def load(self):
        """Loads the model and tokenizer from the specified path."""
        if not FastLanguageModel:
            raise ImportError("Unsloth is required for inference.")

        logger.info(f"Loading model from {self.model_path}...")
        try:
            self.model, self.tokenizer = FastLanguageModel.from_pretrained(
                model_name=self.model_path,
                max_seq_length=4096,
                dtype=None,
                load_in_4bit=True,
            )
            # Optimize tokenizer
            self.tokenizer.padding_side = "left"

            FastLanguageModel.for_inference(self.model)
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def generate(self, prompt: str) -> str:
        """
        Generates a response for the given prompt.
        """
        if not self.model or not self.tokenizer:
            raise RuntimeError("Model not loaded. Call load() first.")

        inputs = self.tokenizer([prompt], return_tensors="pt").to("cuda")

        try:
            with torch.inference_mode():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=2048,
                    use_cache=True,
                    temperature=0.1,  # Low temperature for deterministic analysis
                    do_sample=True,  # Enable sampling for temperature to work
                    top_p=0.95,  # Nucleus sampling
                )

            decoded = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)
            response = decoded[0]

            # Post-processing: extract the response part if the prompt is included
            # The prompt ends with "### Response:\n"
            if "### Response:\n" in response:
                response = response.split("### Response:\n")[-1]

            return response.strip()

        finally:
            # Memory Cleanup
            del inputs
            if "outputs" in locals():
                del outputs
            torch.cuda.empty_cache()
