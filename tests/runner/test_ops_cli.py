import json
import os

from click.testing import CliRunner

from src.core.ai.cache_store import LLMCacheStore
from src.core.config import settings
from src.core.parser.ir import IREdge, IRGraph, IRNode, IRSpan, IRSymbol
from src.core.persistence import get_graph_persistence_service
from src.core.persistence.graph_serializer import build_cache_dir
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

            graph_cache_dir = build_cache_dir(os.getcwd())
            os.makedirs(graph_cache_dir, exist_ok=True)
            graph_cache_path = os.path.join(graph_cache_dir, "stub.jsonl")
            with open(graph_cache_path, "w", encoding="utf-8") as handle:
                handle.write("{}")

            result = runner.invoke(cli, ["ops", "clear-cache"])
            assert result.exit_code == 0

            with open(store.storage_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            assert data == {}
            assert not os.path.exists(graph_cache_dir)
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


def _sample_graph() -> IRGraph:
    span = IRSpan(
        file="sample.py",
        start_line=1,
        start_col=0,
        end_line=1,
        end_col=10,
    )
    node = IRNode(
        id="Func:sample.py:1:0:0",
        kind="Function",
        span=span,
        parent_id=None,
        scope_id="scope:module",
        attrs={"name": "sample"},
    )
    edge = IREdge.model_validate(
        {"from": node.id, "to": node.id, "type": "flow", "guard_id": None}
    )
    symbol = IRSymbol(
        name="sample",
        kind="function",
        scope_id="scope:module",
        defs=[node.id],
        uses=[],
    )
    return IRGraph(nodes=[node], edges=[edge], symbols=[symbol])


def test_ops_graph_export_import():
    runner = CliRunner()
    with runner.isolated_filesystem():
        cwd = os.getcwd()
        graph = _sample_graph()
        sample_path = os.path.join(cwd, "sample.py")
        with open(sample_path, "w", encoding="utf-8") as handle:
            handle.write("def sample():\n    return 1\n")
        get_graph_persistence_service(cwd).save_ir_graph(graph, "sample.py")

        export_path = "exported_graph.jsonl"
        result = runner.invoke(cli, ["ops", "graph-export", "--output", export_path])
        assert result.exit_code == 0
        assert os.path.exists(export_path)

        graph_cache_dir = build_cache_dir(cwd)
        if os.path.exists(graph_cache_dir):
            for entry in os.listdir(graph_cache_dir):
                os.remove(os.path.join(graph_cache_dir, entry))
        result = runner.invoke(cli, ["ops", "graph-import", "--input", export_path])
        assert result.exit_code == 0
        assert os.path.exists(graph_cache_dir)

        loaded_graph, _ = get_graph_persistence_service(cwd).load_project_graph(
            cwd, strict=True
        )
        assert loaded_graph.model_dump(by_alias=True) == graph.model_dump(by_alias=True)
