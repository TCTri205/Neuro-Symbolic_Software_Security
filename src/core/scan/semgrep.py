import json
import os
import subprocess
from typing import Any, Dict


class SemgrepRunner:
    def __init__(
        self, config: str = None, timeout: int = 120, executable: str = "semgrep"
    ):
        self.config = config or os.getenv("SEMGREP_CONFIG", "auto")
        self.timeout = timeout
        self.executable = executable

    def run(self, target: str) -> Dict[str, Any]:
        command = [self.executable, "--json", "--config", self.config, target]
        try:
            env = os.environ.copy()
            env.setdefault("PYTHONUTF8", "1")
            env.setdefault("PYTHONIOENCODING", "utf-8")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                env=env,
            )
        except FileNotFoundError:
            return {
                "error": "semgrep not installed",
                "results": [],
                "errors": [],
            }
        except subprocess.TimeoutExpired:
            return {
                "error": "semgrep timeout",
                "results": [],
                "errors": [],
            }

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        if not stdout.strip():
            return {
                "error": f"semgrep produced no output (code {result.returncode})",
                "results": [],
                "errors": [],
                "stderr": stderr,
            }

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return {
                "error": "semgrep output parse failed",
                "results": [],
                "errors": [],
                "stdout": stdout,
                "stderr": stderr,
            }

        if result.returncode not in (0, 1):
            payload.setdefault("errors", []).append(
                {
                    "level": "error",
                    "message": f"semgrep exited with code {result.returncode}",
                }
            )

        return payload
