#!/usr/bin/env python3
"""
Evaluation script for NSSS Security Auditor model.
Runs the EvaluationHarness against a local or remote provider.

Usage:
    python scripts/evaluate_model.py --provider local --model outputs/qwen-security-model
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.ai.client import AIClientFactory  # noqa: E402
from src.core.finetuning.eval import EvaluationHarness  # noqa: E402
from src.core.finetuning.data_factory import TrainingExample  # noqa: E402
from src.core.finetuning.few_shot_registry import FewShotRegistry  # noqa: E402
from src.core.telemetry import get_logger  # noqa: E402

logger = get_logger(__name__)


def load_validation_data(registry_path: Optional[Path] = None) -> List[TrainingExample]:
    """Loads validation data from registry or creates demo data."""
    if registry_path and registry_path.exists():
        logger.info(f"Loading registry from {registry_path}")
        registry = FewShotRegistry(storage_path=registry_path)
        registry.load()
    else:
        logger.info("Using demo registry for evaluation.")
        registry = FewShotRegistry()
        # Import populate function dynamically to avoid circular imports if any
        from scripts.train_model import populate_demo_registry

        populate_demo_registry(registry)

    raw_data = registry.to_training_format()
    examples = []

    import json

    for item in raw_data:
        # Convert raw dict to TrainingExample
        # Note: 'input' in registry is a Dict, but TrainingExample.input_data is often a string
        # (based on data_factory.py). However, eval.py's harness usually expects string or
        # something it can pass to client.analyze.

        # Let's check eval.py usage:
        # response = self.client.analyze(example.instruction, example.input_data)

        # So if input_data is a dict, client.analyze(str, dict) might fail if client expects str.
        # Most clients expect string prompts.

        inp = item["input"]
        if isinstance(inp, dict):
            inp_str = json.dumps(inp, indent=2)
        else:
            inp_str = str(inp)

        examples.append(
            TrainingExample(
                instruction=item["instruction"],
                input_data=inp_str,
                output_data=item["output"],
            )
        )

    return examples


def main():
    parser = argparse.ArgumentParser(description="Evaluate NSSS Security Model")
    parser.add_argument(
        "--provider",
        default="local",
        choices=["local", "mock", "openai", "gemini"],
        help="LLM Provider",
    )
    parser.add_argument(
        "--model",
        default="outputs/qwen-security-model",
        help="Path to local model or model name",
    )
    parser.add_argument("--registry", type=Path, help="Path to registry file")
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of samples for evaluation"
    )

    args = parser.parse_args()

    import time
    from datetime import datetime

    print("\n" + "=" * 60, flush=True)
    print(f"🚀 EVALUATION START - {datetime.now().strftime('%H:%M:%S')}", flush=True)
    print("=" * 60, flush=True)
    print(f"Provider: {args.provider}", flush=True)
    print(f"Model: {args.model}", flush=True)
    print(f"Registry: {args.registry}", flush=True)
    if args.limit:
        print(f"Sample Limit: {args.limit}", flush=True)
    print("=" * 60 + "\n", flush=True)

    # 1. Setup Client
    print(f"📦 Step 1/4: Initializing {args.provider} client...", flush=True)
    start_step = time.time()
    logger.info(f"Initializing client for provider: {args.provider}")
    client = AIClientFactory.get_client(provider=args.provider, model=args.model)
    print(f"   ✅ Client initialized in {time.time()-start_step:.1f}s\n", flush=True)

    if args.provider == "local":
        print(f"📥 Step 2/4: Loading local model from {args.model}...", flush=True)
        print(
            "   ⏳ This may take 2-5 minutes (downloading + loading 7B model)...",
            flush=True,
        )
        start_step = time.time()
        logger.info(f"Loading local model from {args.model}...")
        try:
            client.load_model()
            print(
                f"   ✅ Model loaded successfully in {time.time()-start_step:.1f}s\n",
                flush=True,
            )
        except ImportError as e:
            logger.error(f"Failed to load local model: {e}")
            logger.error("Ensure unsloth is installed if using 'local' provider.")
            print(f"   ❌ Model load failed: {e}", flush=True)
            return 1
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            print(f"   ❌ Model load failed: {e}", flush=True)
            return 1
    else:
        print("📥 Step 2/4: Remote provider - skipping model load\n", flush=True)

    # 2. Load Data
    print("📊 Step 3/4: Loading validation data...", flush=True)
    start_step = time.time()
    examples = load_validation_data(args.registry)

    if args.limit and args.limit > 0:
        logger.info(f"Limiting evaluation to first {args.limit} examples.")
        examples = examples[: args.limit]

    logger.info(f"Loaded {len(examples)} examples for evaluation.")
    print(
        f"   ✅ Loaded {len(examples)} examples in {time.time()-start_step:.1f}s\n",
        flush=True,
    )

    # 3. Run Evaluation
    print("🔬 Step 4/4: Running evaluation...", flush=True)
    print(f"   📌 Total samples: {len(examples)}", flush=True)
    if len(examples) > 0:
        avg_estimate = 15  # seconds per sample (conservative estimate)
        estimated_time = (len(examples) * avg_estimate) / 60
        print(
            f"   ⏱️  Estimated time: ~{estimated_time:.1f} minutes ({avg_estimate}s/sample)",
            flush=True,
        )
    print("", flush=True)

    start_eval = time.time()
    harness = EvaluationHarness(llm_client=client)
    logger.info("Starting evaluation batch...")

    metrics = harness.evaluate_batch(examples)

    eval_time = time.time() - start_eval
    print(f"\n   ⏱️  Total evaluation time: {eval_time/60:.2f} minutes", flush=True)

    # 4. Report Results
    print("\n" + "=" * 40)
    print(" EVALUATION RESULTS")
    print("=" * 40)
    print(f"Total Samples:      {metrics.total_samples}")
    print(f"JSON Validity Rate: {metrics.json_validity_rate:.2%}")
    print(f"Accuracy:           {metrics.accuracy:.2%}")
    print(f"False Positive Rate:{metrics.fpr:.2%}")
    print(f"False Negative Rate:{metrics.fnr:.2%}")
    print("=" * 40 + "\n")

    # 5. Export JSON Report
    import json
    import time

    report = {
        "timestamp": time.time(),
        "provider": args.provider,
        "model": args.model,
        "metrics": {
            "total_samples": metrics.total_samples,
            "json_validity_rate": metrics.json_validity_rate,
            "accuracy": metrics.accuracy,
            "fpr": metrics.fpr,
            "fnr": metrics.fnr,
        },
    }

    # Save to outputs
    output_path = Path("outputs") / "evaluation_report.json"
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Report saved to {output_path}")

    return 0


if __name__ == "__main__":
    logging_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    import logging

    logging.basicConfig(level=logging.INFO, format=logging_format)
    sys.exit(main())
