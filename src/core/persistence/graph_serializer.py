from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Optional, Tuple, Union

from src.core.parser.ir import IRGraph, IREdge, IRNode, IRSymbol


GRAPH_CACHE_FILENAME = "graph_v1.jsonl"


def compute_project_hash(project_root: str) -> str:
    normalized = os.path.abspath(project_root).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def build_cache_path(project_root: str, filename: str = GRAPH_CACHE_FILENAME) -> str:
    project_hash = compute_project_hash(project_root)
    return os.path.join(project_root, ".nsss", "cache", project_hash, filename)


def read_git_commit_hash(project_root: str) -> Optional[str]:
    git_head_path = os.path.join(project_root, ".git", "HEAD")
    if not os.path.exists(git_head_path):
        return None
    try:
        with open(git_head_path, "r", encoding="utf-8") as f:
            head = f.read().strip()
        if head.startswith("ref:"):
            ref_path = head.split(" ", 1)[1].strip()
            ref_full_path = os.path.join(project_root, ".git", ref_path)
            if os.path.exists(ref_full_path):
                with open(ref_full_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            return None
        return head or None
    except OSError:
        return None


@dataclass(frozen=True)
class GraphMeta:
    version: str
    timestamp: int
    project_root: str
    commit_hash: str
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "type": "meta",
            "version": self.version,
            "timestamp": self.timestamp,
            "project_root": self.project_root,
            "commit_hash": self.commit_hash,
        }
        if self.file_path:
            payload["file_path"] = self.file_path
        return payload


class JsonlGraphSerializer:
    def __init__(self, version: str = "1.0") -> None:
        self.version = version

    def save(
        self,
        graph: Union[IRGraph, Dict[str, Any]],
        output_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GraphMeta:
        graph_model = self._coerce_graph(graph)
        meta = self._build_meta(metadata)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(meta.to_dict()) + "\n")
            for node in graph_model.nodes:
                payload = node.model_dump(mode="json")
                payload["record_type"] = "node"
                f.write(json.dumps(payload) + "\n")
            for edge in graph_model.edges:
                payload = edge.model_dump(mode="json", by_alias=True)
                payload["record_type"] = "edge"
                f.write(json.dumps(payload) + "\n")
            for symbol in graph_model.symbols:
                payload = symbol.model_dump(mode="json")
                payload["record_type"] = "symbol"
                f.write(json.dumps(payload) + "\n")
        return meta

    def load(self, input_path: str) -> Tuple[IRGraph, Dict[str, Any]]:
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Graph cache not found: {input_path}")
        graph = IRGraph()
        meta: Optional[Dict[str, Any]] = None
        with open(input_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                entry_type = payload.get("record_type")
                if entry_type is None:
                    entry_type = payload.get("type")
                    if entry_type not in {"meta", "node", "edge", "symbol"}:
                        entry_type = None
                if idx == 0:
                    if entry_type != "meta":
                        raise ValueError("First line must be meta")
                    if payload.get("version") != self.version:
                        raise ValueError(
                            "Unsupported graph version: " f"{payload.get('version')}"
                        )
                    meta = payload
                    continue
                if entry_type == "node":
                    graph.add_node(IRNode.model_validate(payload))
                elif entry_type == "edge":
                    graph.add_edge(IREdge.model_validate(payload))
                elif entry_type == "symbol":
                    graph.symbols.append(IRSymbol.model_validate(payload))
        if meta is None:
            raise ValueError("Missing graph metadata")
        return graph, meta

    def _coerce_graph(self, graph: Union[IRGraph, Dict[str, Any]]) -> IRGraph:
        if isinstance(graph, IRGraph):
            return graph
        return IRGraph.model_validate(graph)

    def _build_meta(self, metadata: Optional[Dict[str, Any]]) -> GraphMeta:
        data = metadata or {}
        project_root = os.path.abspath(data.get("project_root") or os.getcwd())
        commit_hash = data.get("commit_hash") or read_git_commit_hash(project_root)
        if not commit_hash:
            commit_hash = "unknown"
        return GraphMeta(
            version=self.version,
            timestamp=int(data.get("timestamp") or time.time()),
            project_root=project_root,
            commit_hash=commit_hash,
            file_path=data.get("file_path"),
        )


class GraphPersistenceService:
    _instance: Optional["GraphPersistenceService"] = None
    _lock: Lock = Lock()

    def __init__(self, serializer: Optional[JsonlGraphSerializer] = None) -> None:
        self._serializer = serializer or JsonlGraphSerializer()

    @classmethod
    def get_instance(cls) -> "GraphPersistenceService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = GraphPersistenceService()
            return cls._instance

    def save_ir_graph(
        self,
        graph: Union[IRGraph, Dict[str, Any]],
        file_path: str,
        project_root: Optional[str] = None,
    ) -> str:
        root = os.path.abspath(project_root or os.getcwd())
        cache_path = build_cache_path(root)
        self._serializer.save(
            graph,
            cache_path,
            metadata={
                "project_root": root,
                "commit_hash": read_git_commit_hash(root),
                "file_path": file_path,
            },
        )
        return cache_path

    def load_ir_graph(self, project_root: Optional[str] = None) -> Tuple[IRGraph, Dict]:
        root = os.path.abspath(project_root or os.getcwd())
        cache_path = build_cache_path(root)
        return self._serializer.load(cache_path)
