"""NSSS demo client for Colab inference API."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict

import requests


def build_payload() -> Dict[str, Any]:
    return {
        "function_signature": (
            "def get_user(uid):\n"
            "    query = f'SELECT * FROM users WHERE id = {uid}'\n"
            "    cursor.execute(query)"
        ),
        "language": "python",
        "vulnerability_type": "SQL Injection",
        "context": {
            "source_variable": "uid",
            "sink_function": "cursor.execute",
            "line_number": 2,
            "file_path": "vulnerable_app.py",
            "sanitizers_found": [],
        },
        "privacy_mask": {"enabled": True, "map": {}},
        "metadata": {"mode": "precision", "request_id": "demo-req-001"},
    }


def run_demo(url: str, api_key: str) -> bool:
    endpoint = f"{url.rstrip('/')}/analyze"
    payload = build_payload()
    headers = {"X-API-Key": api_key} if api_key else {}

    print(f"Testing endpoint: {endpoint}")
    try:
        start_time = time.time()
        response = requests.post(endpoint, json=payload, headers=headers, timeout=60)
        duration = time.time() - start_time

        print(f"Status Code: {response.status_code}")
        print(f"Time Taken: {duration:.2f}s")

        if response.status_code == 200:
            data = response.json()
            print("\nResponse Data:")
            print(json.dumps(data, indent=2))
            return data.get("status") == "success"

        print(f"Error Response: {response.text}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to {url}. Is the server running?")
        return False
    except Exception as exc:
        print(f"❌ Error: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NSSS demo client")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the Colab server",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="Optional X-API-Key for the server",
    )
    args = parser.parse_args()

    success = run_demo(args.url, args.api_key)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
