#!/usr/bin/env python3
"""
Run the Joern stub pipeline and export NSSS IR JSON.

Usage:
    python scripts/run_joern_stub.py
    python scripts/run_joern_stub.py --file samples/joern_stub/hello.c --output joern_stub_ir.json
"""

import argparse
from pathlib import Path

from src.core.interop import export_stub_ir
from src.core.telemetry import get_logger

logger = get_logger(__name__)


def build_default_input() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "samples" / "joern_stub" / "hello.c"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Joern stub pipeline")
    parser.add_argument(
        "--file",
        dest="file_path",
        default=str(build_default_input()),
        help="Input source file to parse",
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        default="joern_stub_ir.json",
        help="Output JSON path for exported IR",
    )
    return parser.parse_args()


def run(file_path: Path, output_path: Path) -> int:
    if not file_path.exists():
        logger.error("Input file not found: %s", file_path)
        return 1

    export_stub_ir(str(file_path), str(output_path))
    logger.info("Stub pipeline complete: %s", output_path)
    return 0


def main() -> int:
    args = parse_args()
    return run(Path(args.file_path), Path(args.output_path))


if __name__ == "__main__":
    raise SystemExit(main())
