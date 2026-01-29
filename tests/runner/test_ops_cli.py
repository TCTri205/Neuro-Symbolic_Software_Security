import json
import os

from click.testing import CliRunner

from src.core.ai.cache_store import LLMCacheStore
from src.core.config import settings
from src.core.persistence.graph_serializer import build_cache_path
from src.runner.cli.main import cli


def test_ops_clear_cache():
    runner = CliRunner()
    original_cache_path = settings.LLM_CACHE_PATH
    try:
        with runner.isolated_filesystem():
            settings.LLM_CACHE_PATH = ".nsss/cache/llm_cache.json"
            LLMCacheStore._instance = None
            store = LLMCacheStore.get_instance()
            store.set("key", "value")

            graph_cache_path = build_cache_path(os.getcwd())
            os.makedirs(os.path.dirname(graph_cache_path), exist_ok=True)
            with open(graph_cache_path, "w", encoding="utf-8") as handle:
                handle.write("{}")

            result = runner.invoke(cli, ["ops", "clear-cache"])
            assert result.exit_code == 0

            with open(store.storage_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            assert data == {}
            assert not os.path.exists(graph_cache_path)
    finally:
        settings.LLM_CACHE_PATH = original_cache_path
        LLMCacheStore._instance = None


def test_ops_health_basic():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["ops", "health"])
        assert result.exit_code == 0
        assert "NSSS Ops Health Check" in result.output
        assert "LLM cache:" in result.output


def test_ops_rotate_logs():
    runner = CliRunner()
    with runner.isolated_filesystem():
        log_path = os.path.join(".nsss", "logs", "nsss.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write("log data")

        result = runner.invoke(
            cli,
            ["ops", "rotate-logs", "--log-file", log_path, "--keep", "1"],
        )
        assert result.exit_code == 0

        assert os.path.exists(log_path)
        with open(log_path, "r", encoding="utf-8") as handle:
            assert handle.read() == ""

        rotated = [
            entry
            for entry in os.listdir(os.path.dirname(log_path))
            if entry.startswith("nsss.log.")
        ]
        assert len(rotated) == 1
