from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Optional, Tuple, Union

from src.core.parser.ir import IRGraph, IREdge, IRNode, IRSymbol
from src.core.telemetry import get_logger


GRAPH_CACHE_FILENAME = "graph_v1.jsonl"
MANIFEST_FILENAME = "manifest.json"

logger = get_logger(__name__)


def compute_project_hash(project_root: str) -> str:
    normalized = os.path.abspath(project_root).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def build_cache_path(project_root: str, filename: str = GRAPH_CACHE_FILENAME) -> str:
    project_hash = compute_project_hash(project_root)
    return os.path.join(project_root, ".nsss", "cache", project_hash, filename)


def build_manifest_path(project_root: str) -> str:
    return build_cache_path(project_root, MANIFEST_FILENAME)


def compute_file_hash(file_path: str) -> Optional[str]:
    if not os.path.exists(file_path):
        return None
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                hasher.update(chunk)
    except OSError:
        return None
    return hasher.hexdigest()


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


@dataclass(frozen=True)
class GraphManifestEntry:
    file_path: str
    file_hash: str
    cache_path: str
    updated_at: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "cache_path": self.cache_path,
            "updated_at": self.updated_at,
        }


@dataclass
class GraphManifest:
    version: str
    updated_at: int
    entries: Dict[str, GraphManifestEntry]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "entries": {key: entry.to_dict() for key, entry in self.entries.items()},
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GraphManifest":
        entries = {
            key: GraphManifestEntry(**entry)
            for key, entry in payload.get("entries", {}).items()
        }
        return cls(
            version=payload.get("version", "1.0"),
            updated_at=int(payload.get("updated_at", 0)),
            entries=entries,
        )


class GraphManifestStore:
    def __init__(self, project_root: str, version: str = "1.0") -> None:
        self._lock = Lock()
        self.project_root = os.path.abspath(project_root)
        self.version = version
        self.manifest_path = build_manifest_path(self.project_root)
        self._manifest = GraphManifest(version=version, updated_at=0, entries={})
        self._load()

    def record(self, file_path: str, cache_path: str) -> Optional[GraphManifestEntry]:
        file_hash = compute_file_hash(file_path)
        if not file_hash:
            return None
        normalized = self._normalize_file_path(file_path)
        timestamp = int(time.time())
        entry = GraphManifestEntry(
            file_path=normalized,
            file_hash=file_hash,
            cache_path=cache_path,
            updated_at=timestamp,
        )
        with self._lock:
            self._manifest.entries[normalized] = entry
            self._manifest.updated_at = timestamp
            self._persist()
        return entry

    def is_fresh(self, file_path: str) -> bool:
        file_hash = compute_file_hash(file_path)
        if not file_hash:
            return False
        normalized = self._normalize_file_path(file_path)
        entry = self._manifest.entries.get(normalized)
        return entry is not None and entry.file_hash == file_hash

    def get_entry(self, file_path: str) -> Optional[GraphManifestEntry]:
        normalized = self._normalize_file_path(file_path)
        return self._manifest.entries.get(normalized)

    def _normalize_file_path(self, file_path: str) -> str:
        abs_path = os.path.abspath(file_path)
        try:
            return os.path.relpath(abs_path, self.project_root)
        except ValueError:
            return abs_path

    def _load(self) -> None:
        if not os.path.exists(self.manifest_path):
            return
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self._manifest = GraphManifest.from_dict(payload)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to load graph manifest: {exc}")

    def _persist(self) -> None:
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(self._manifest.to_dict(), handle, indent=2)


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
        self._update_manifest(root, file_path, cache_path)
        return cache_path

    def load_ir_graph(self, project_root: Optional[str] = None) -> Tuple[IRGraph, Dict]:
        root = os.path.abspath(project_root or os.getcwd())
        cache_path = build_cache_path(root)
        return self._serializer.load(cache_path)

    def _update_manifest(
        self, project_root: str, file_path: str, cache_path: str
    ) -> None:
        if not file_path:
            return
        store = GraphManifestStore(project_root, version=self._serializer.version)
        entry = store.record(file_path, cache_path)
        if entry is None:
            logger.debug("Skipping manifest update; file hash unavailable")
