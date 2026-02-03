#!/usr/bin/env python3
"""
Training script for NSSS Security Auditor model.

Implements training workflow with FewShotRegistry integration.
See Doc 06 (Fine-tuning Strategy) for architecture details.

Usage:
    python scripts/train_model.py --registry data/few_shot_registry.json --output outputs/qwen-security-model
"""

import argparse
import json
import tempfile
import sys
from pathlib import Path

# Ensure src is in path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.finetuning.few_shot_registry import FewShotRegistry
from src.core.finetuning.trainer import Finetuner
from src.core.telemetry import get_logger

logger = get_logger(__name__)


def populate_demo_registry(registry: FewShotRegistry) -> None:
    """
    Populate registry with demo security examples for POC training.

    This function creates synthetic training data covering the vulnerability types
    defined in Doc 02 (Python Vulnerability Map).
    """
    logger.info("Populating registry with demo examples...")

    # SQL Injection Examples
    registry.add_fix_example(
        code_before="def get_user(uid):\n    sql = f'SELECT * FROM users WHERE id = {uid}'\n    cursor.execute(sql)",
        code_after="def get_user(uid):\n    sql = 'SELECT * FROM users WHERE id = %s'\n    cursor.execute(sql, (uid,))",
        vuln_type="SQL Injection",
        source="Demo-SQLi-001",
    )

    registry.add_positive_example(
        code='def login(username, password):\n    query = "SELECT * FROM users WHERE user=\'" + username + "\'"\n    cursor.execute(query)',
        vuln_type="SQL Injection",
        reasoning="String concatenation with user input in SQL query enables SQL injection. Attacker can inject malicious SQL.",
        source="Manual Review",
    )

    # XSS Examples
    registry.add_positive_example(
        code="def render_comment(user_input):\n    return f'<div>{user_input}</div>'",
        vuln_type="XSS",
        reasoning="User input is directly embedded in HTML without sanitization. Attacker can inject <script> tags.",
        source="Manual Review",
    )

    registry.add_false_positive(
        code="def render_comment(user_input):\n    import html\n    safe = html.escape(user_input)\n    return f'<div>{safe}</div>'",
        vuln_type="XSS",
        reason="html.escape properly neutralizes HTML special characters, preventing XSS.",
        triaged_by="Security Analyst",
    )

    # Code Injection Examples
    registry.add_fix_example(
        code_before="def process_expr(user_expr):\n    result = eval(user_expr)\n    return result",
        code_after="def process_expr(user_expr):\n    import ast\n    result = ast.literal_eval(user_expr)\n    return result",
        vuln_type="Code Injection",
        source="Demo-CodeInj-001",
    )

    # Path Traversal Examples
    registry.add_positive_example(
        code="def read_file(filename):\n    path = '/var/uploads/' + filename\n    with open(path) as f:\n        return f.read()",
        vuln_type="Path Traversal",
        reasoning="Direct concatenation of user input with file path allows path traversal attacks (../../etc/passwd).",
        source="Manual Review",
    )

    registry.add_false_positive(
        code="def read_file(filename):\n    import os\n    safe_name = os.path.basename(filename)\n    path = os.path.join('/var/uploads', safe_name)\n    with open(path) as f:\n        return f.read()",
        vuln_type="Path Traversal",
        reason="os.path.basename removes directory components, preventing path traversal.",
        triaged_by="Security Analyst",
    )

    # Command Injection Examples
    registry.add_fix_example(
        code_before="def ping_host(hostname):\n    import os\n    os.system(f'ping -c 4 {hostname}')",
        code_after="def ping_host(hostname):\n    import subprocess\n    subprocess.run(['ping', '-c', '4', hostname], check=True)",
        vuln_type="Command Injection",
        source="Demo-CmdInj-001",
    )

    # XXE Examples
    registry.add_positive_example(
        code="def parse_xml(xml_data):\n    import xml.etree.ElementTree as ET\n    tree = ET.fromstring(xml_data)\n    return tree",
        vuln_type="XXE",
        reasoning="xml.etree.ElementTree is vulnerable to XXE attacks if DTDs are not disabled.",
        source="Manual Review",
    )

    # Deserialization Examples
    registry.add_positive_example(
        code="def load_session(session_data):\n    import pickle\n    session = pickle.loads(session_data)\n    return session",
        vuln_type="Insecure Deserialization",
        reasoning="pickle.loads on untrusted data allows arbitrary code execution through malicious pickle payloads.",
        source="Manual Review",
    )

    logger.info(f"Added {len(registry.examples)} examples to registry")


def main():
    parser = argparse.ArgumentParser(
        description="Train NSSS Security Auditor model using FewShotRegistry"
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="Path to existing few_shot_registry.json (optional)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/qwen-security-model"),
        help="Output directory for trained model",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="Qwen/Qwen2.5-Coder-7B-Instruct",
        help="Base model to fine-tune",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use demo examples instead of loading from registry file",
    )
    parser.add_argument(
        "--save-dataset",
        type=Path,
        help="Save training dataset to JSONL file (for inspection)",
    )

    args = parser.parse_args()

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Load or create registry
    if args.demo:
        logger.info("Creating demo registry...")
        registry = FewShotRegistry()
        populate_demo_registry(registry)
    elif args.registry and args.registry.exists():
        logger.info(f"Loading registry from {args.registry}")
        registry = FewShotRegistry(storage_path=args.registry)
        registry.load()
    else:
        logger.warning("No registry provided. Creating empty registry with demo data.")
        registry = FewShotRegistry()
        populate_demo_registry(registry)

    # Convert to training format
    logger.info("Converting examples to training format...")
    training_data = registry.to_training_format()

    if len(training_data) == 0:
        logger.error("No training examples found. Aborting.")
        return 1

    logger.info(f"Training dataset size: {len(training_data)} examples")

    # Save dataset if requested
    if args.save_dataset:
        logger.info(f"Saving training dataset to {args.save_dataset}")
        with open(args.save_dataset, "w", encoding="utf-8") as f:
            for example in training_data:
                f.write(json.dumps(example) + "\n")

    # Create temporary dataset file for HuggingFace datasets
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as tmp_dataset:
        for example in training_data:
            tmp_dataset.write(json.dumps(example) + "\n")
        dataset_path = tmp_dataset.name

    logger.info(f"Temporary dataset created at {dataset_path}")

    # Initialize trainer
    logger.info(f"Initializing Finetuner with model: {args.model}")
    finetuner = Finetuner(model_name=args.model)

    # Train
    logger.info("Starting training...")
    logger.info(f"Output directory: {args.output}")

    try:
        finetuner.train(dataset_path=dataset_path, output_dir=str(args.output))
        logger.info("✅ Training completed successfully!")
        logger.info(f"Model saved to: {args.output}")
        logger.info("\nNext steps:")
        logger.info("1. Test the model with: python scripts/test_trained_model.py")
        logger.info("2. Deploy to Colab Server for production use")
        return 0

    except Exception as e:
        logger.error(f"❌ Training failed: {e}", exc_info=True)
        return 1

    finally:
        # Cleanup temporary file
        Path(dataset_path).unlink(missing_ok=True)


if __name__ == "__main__":
    exit(main())
