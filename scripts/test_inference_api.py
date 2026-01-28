#!/usr/bin/env python3
"""
Integration test for the Colab Inference API.
Mimics a Laptop Client sending a request to the server.

Usage:
    python scripts/test_inference_api.py --url http://localhost:8000
"""

import argparse
import requests
import json
import sys
import time


def test_api(url: str):
    endpoint = f"{url}/analyze"
    print(f"Testing endpoint: {endpoint}")

    # Sample vulnerable code (SQL Injection)
    # Must match src.core.ai.protocol.AnalysisRequest schema
    payload = {
        "function_signature": "def get_user(uid):\n    sql = f'SELECT * FROM users WHERE id = {uid}'\n    cursor.execute(sql)",
        "language": "python",
        "vulnerability_type": "SQL Injection",
        "context": {
            "source_variable": "uid",
            "sink_function": "cursor.execute",
            "line_number": 2,
            "file_path": "auth.py",
        },
        "privacy_mask": {"enabled": True, "map": {}},
        "metadata": {"mode": "precision", "request_id": "test-req-001"},
    }

    try:
        start_time = time.time()
        response = requests.post(endpoint, json=payload, timeout=60)
        duration = time.time() - start_time

        print(f"Status Code: {response.status_code}")
        print(f"Time Taken: {duration:.2f}s")

        if response.status_code == 200:
            data = response.json()
            print("\nResponse Data:")
            print(json.dumps(data, indent=2))

            # Basic validation
            if data["status"] == "success":
                analysis = data["data"]
                print(
                    f"\nAnalysis Summary: {analysis.get('analysis_summary')[:100]}..."
                )
                print(f"Is Vulnerable: {analysis.get('is_vulnerable')}")
                return True
            else:
                print("Analysis failed.")
                return False
        else:
            print(f"Error Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to {url}. Is the server running?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Inference API")
    parser.add_argument(
        "--url", default="http://localhost:8000", help="Base URL of the server"
    )
    args = parser.parse_args()

    success = test_api(args.url)
    sys.exit(0 if success else 1)
