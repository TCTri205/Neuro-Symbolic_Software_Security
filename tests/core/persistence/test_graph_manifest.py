from src.core.persistence.graph_serializer import GraphManifestStore


def test_graph_manifest_records_and_checks_hash(tmp_path):
    source_path = tmp_path / "sample.py"
    source_path.write_text("print('hello')", encoding="utf-8")

    store = GraphManifestStore(str(tmp_path))
    entry = store.record(str(source_path), "graph_v1.jsonl")

    assert entry is not None
    assert store.is_fresh(str(source_path))

    source_path.write_text("print('hello world')", encoding="utf-8")
    assert not store.is_fresh(str(source_path))
