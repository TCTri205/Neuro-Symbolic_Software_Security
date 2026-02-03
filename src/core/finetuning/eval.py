import json
import dataclasses
from typing import List, Dict, Any, Optional
from src.core.telemetry import get_logger
from src.core.finetuning.data_factory import TrainingExample
from src.core.ai.cot import extract_cot

try:
    from tqdm.auto import tqdm  # auto selects best UI (notebook vs terminal)
except ImportError:
    # Fallback if tqdm is not installed
    def tqdm(iterable, desc="", **kwargs):
        print(f"Start processing: {desc}")
        return iterable


logger = get_logger(__name__)


@dataclasses.dataclass
class EvaluationMetrics:
    total_samples: int
    json_validity_rate: float
    accuracy: float
    fpr: float  # False Positive Rate
    fnr: float  # False Negative Rate
    fix_rate: float = 0.0  # Optional


class EvaluationHarness:
    """
    Evaluates a model (LLM) against a set of TrainingExamples.
    """

    def __init__(self, llm_client):
        self.client = llm_client

    def evaluate_batch(self, examples: List[TrainingExample]) -> EvaluationMetrics:
        """
        Runs evaluation on a batch of examples.
        """
        import time

        valid_json_count = 0
        correct_predictions = 0

        # Confusion Matrix
        tp = 0
        tn = 0
        fp = 0
        fn = 0

        total = len(examples)
        if total == 0:
            return EvaluationMetrics(0, 0.0, 0.0, 0.0, 0.0)

        logger.info(f"Starting evaluation of {total} examples...")
        print(f"🔄 Processing {total} samples...", flush=True)

        # Progress tracking
        start_time = time.time()
        log_interval = max(1, total // 20)  # Log every 5% progress

        for idx, example in enumerate(
            tqdm(examples, desc="Evaluating", unit="sample"), 1
        ):
            # Log progress every N samples
            if idx % log_interval == 0 or idx == 1:
                elapsed = time.time() - start_time
                avg_time = elapsed / idx
                remaining = (total - idx) * avg_time
                print(
                    f"   [{idx}/{total}] {idx/total*100:.1f}% | "
                    f"Elapsed: {elapsed/60:.1f}m | "
                    f"ETA: {remaining/60:.1f}m | "
                    f"Avg: {avg_time:.1f}s/sample",
                    flush=True,
                )

            # 1. Use client.analyze interface which handles formatting
            try:
                # Some clients might return a dict with "content"
                response = self.client.analyze(example.instruction, example.input_data)
                if isinstance(response, dict):
                    # Fallback if client returns full dict instead of string
                    response = response.get("content", "")
            except Exception as e:
                logger.error(f"Generation failed at sample {idx}: {e}")
                print(f"   ⚠️ Sample {idx} failed: {e}", flush=True)
                # Treat as invalid
                continue

            # 2. Parse Response
            parsed_output = self._parse_response(response)

            if parsed_output is None:
                # Invalid JSON
                # If ground truth was Safe (False), and we failed to output valid JSON,
                # does it count as FP or FN?
                # Usually we just penalize validity and maybe accuracy (treat as wrong).
                # Here we treat it as "incorrect" but not specifically FP/FN unless we assume a default.
                # Let's count it as incorrect for accuracy, but exclude from FP/FN calculations
                # OR treat it as a specific class.
                # For simplicity in this implementation:
                # If invalid, it contributes to neither TP, TN, FP, FN directly in some schemas,
                # but usually it's a "Miss".
                # Let's see how the test expects it.
                # test_eval_harness_invalid_json expects accuracy = 0.0.
                pass
            else:
                valid_json_count += 1

                # 3. Compare with Ground Truth
                ground_truth_vuln = example.output_data.get("is_vulnerable", False)
                predicted_vuln = parsed_output.get(
                    "is_vulnerable", False
                )  # Default to False if key missing?

                if predicted_vuln == ground_truth_vuln:
                    correct_predictions += 1
                    if ground_truth_vuln:
                        tp += 1
                    else:
                        tn += 1
                else:
                    if predicted_vuln and not ground_truth_vuln:
                        fp += 1
                    elif not predicted_vuln and ground_truth_vuln:
                        fn += 1

        # Calculate Rates
        accuracy = correct_predictions / total
        json_validity = valid_json_count / total

        # FPR = FP / (FP + TN)
        negatives = fp + tn
        fpr = fp / negatives if negatives > 0 else 0.0

        # FNR = FN / (FN + TP)
        positives = fn + tp
        fnr = fn / positives if positives > 0 else 0.0

        total_time = time.time() - start_time
        print(f"\n✅ Evaluation completed in {total_time/60:.1f} minutes", flush=True)
        logger.info(f"Evaluation completed. Total time: {total_time:.1f}s")

        return EvaluationMetrics(
            total_samples=total,
            json_validity_rate=json_validity,
            accuracy=accuracy,
            fpr=fpr,
            fnr=fnr,
        )

    def _parse_response(self, response: str) -> Optional[Dict[str, Any]]:
        try:
            # Remove <thinking>
            json_part, _ = extract_cot(response)

            # Clean Markdown
            json_part = json_part.strip()
            if json_part.startswith("```json"):
                json_part = json_part[7:]
            if json_part.startswith("```"):
                json_part = json_part[
                    3:
                ]  # Usually ``` at start, but checking just in case
            if json_part.endswith("```"):
                json_part = json_part[:-3]

            return json.loads(json_part.strip())
        except (json.JSONDecodeError, ValueError):
            return None
