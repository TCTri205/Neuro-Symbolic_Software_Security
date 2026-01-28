from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from src.core.telemetry import get_logger


class BaselineEntry(BaseModel):
    fingerprint: str
    rule_id: str
    file: str
    line: int
    column: int
    sink: str
    source: str
    code_hash: str
    created_at: str


class BaselineData(BaseModel):
    version: str
    generated_at: str
    project_root: str
    entries: List[BaselineEntry]


class BaselineEngine:
    def __init__(
        self,
        storage_path: str = ".nsss/baseline.json",
        project_root: Optional[str] = None,
    ):
        if not os.path.isabs(storage_path):
            storage_path = os.path.join(os.getcwd(), storage_path)

        self.storage_path = storage_path
        self.project_root = project_root or os.getcwd()
        self.logger = get_logger(__name__)
        self._entries: Dict[str, BaselineEntry] = {}
        self._observed: set[str] = set()
        self._stats: Dict[str, int] = {"new": 0, "existing": 0}
        self.load()

    def load(self) -> BaselineData:
        if not os.path.exists(self.storage_path):
            data = self._empty_baseline()
            self._entries = {}
            return data

        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                content = handle.read()
            if not content:
                data = self._empty_baseline()
                self._entries = {}
                return data
            payload = json.loads(content)
            data = BaselineData(**payload)
            self._entries = {entry.fingerprint: entry for entry in data.entries}
            return data
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            self.logger.error(f"Failed to load baseline data: {exc}")
            data = self._empty_baseline()
            self._entries = {}
            return data

    def save(self, entries: List[BaselineEntry]) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        data = BaselineData(
            version="1.0",
            generated_at=self._now_iso(),
            project_root=self.project_root,
            entries=entries,
        )
        with open(self.storage_path, "w", encoding="utf-8") as handle:
            json.dump(data.model_dump(mode="json"), handle, indent=2)
        self._entries = {entry.fingerprint: entry for entry in entries}

    def build_entries(
        self, findings: List[Dict[str, Any]], file_path: str, source_lines: List[str]
    ) -> List[BaselineEntry]:
        entries: List[BaselineEntry] = []
        for finding in findings:
            entry = self._build_entry(finding, file_path, source_lines)
            if entry:
                entries.append(entry)
        return entries

    def filter_findings(
        self, findings: List[Dict[str, Any]], file_path: str, source_lines: List[str]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        new_findings: List[Dict[str, Any]] = []
        new_count = 0
        existing_count = 0

        for finding in findings:
            entry = self._build_entry(finding, file_path, source_lines)
            if not entry:
                new_findings.append(finding)
                new_count += 1
                continue

            self._observed.add(entry.fingerprint)
            if entry.fingerprint in self._entries:
                existing_count += 1
                continue

            new_findings.append(finding)
            new_count += 1

        self._stats["new"] += new_count
        self._stats["existing"] += existing_count
        return new_findings, {"new": new_count, "existing": existing_count}

    def summary(self) -> Dict[str, int]:
        total = len(self._entries)
        resolved = total - len(self._entries.keys() & self._observed)
        return {
            "total": total,
            "new": self._stats["new"],
            "existing": self._stats["existing"],
            "resolved": max(resolved, 0),
        }

    def fingerprint_for_finding(
        self, finding: Dict[str, Any], file_path: str, source_lines: List[str]
    ) -> str:
        entry = self._build_entry(finding, file_path, source_lines)
        return entry.fingerprint if entry else ""

    def _build_entry(
        self, finding: Dict[str, Any], file_path: str, source_lines: List[str]
    ) -> Optional[BaselineEntry]:
        rule_id = self._extract_rule_id(finding)
        line = self._extract_int(finding, "line", default=1)
        column = self._extract_int(finding, "column", default=1)
        sink, source = self._extract_sink_source(finding)

        end_line = self._extract_end_line(finding, line)
        snippet_lines = self._extract_snippet_lines(source_lines, line, end_line)
        normalized = self._normalize_snippet(snippet_lines)
        code_hash = self._hash_snippet(normalized)

        normalized_path = self._normalize_file_path(file_path)
        fingerprint = self._build_fingerprint(
            rule_id=rule_id,
            file_path=normalized_path,
            line=line,
            column=column,
            sink=sink,
            source=source,
            code_hash=code_hash,
        )

        return BaselineEntry(
            fingerprint=fingerprint,
            rule_id=rule_id,
            file=normalized_path,
            line=line,
            column=column,
            sink=sink,
            source=source,
            code_hash=code_hash,
            created_at=self._now_iso(),
        )

    @staticmethod
    def _extract_rule_id(finding: Dict[str, Any]) -> str:
        for key in ("rule_id", "check_id", "id"):
            value = finding.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "UNKNOWN"

    @staticmethod
    def _extract_int(finding: Dict[str, Any], key: str, default: int = 1) -> int:
        value = finding.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return default

    @staticmethod
    def _extract_end_line(finding: Dict[str, Any], start_line: int) -> int:
        for key in ("end_line", "endLine"):
            value = finding.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        end_block = finding.get("end")
        if isinstance(end_block, dict):
            value = end_block.get("line")
            if isinstance(value, int):
                return value
        return start_line

    @staticmethod
    def _extract_sink_source(finding: Dict[str, Any]) -> Tuple[str, str]:
        metadata = finding.get("metadata") or {}
        sink = finding.get("sink") or metadata.get("sink") or ""
        source = finding.get("source") or metadata.get("source") or ""
        return str(sink), str(source)

    def _normalize_file_path(self, file_path: str) -> str:
        normalized = file_path
        if os.path.isabs(file_path):
            try:
                normalized = os.path.relpath(file_path, self.project_root)
            except ValueError:
                normalized = file_path
        return normalized.replace("\\", "/")

    @staticmethod
    def _extract_snippet_lines(
        source_lines: List[str], start_line: int, end_line: int
    ) -> List[str]:
        if not source_lines:
            return []
        start_line = max(start_line, 1)
        end_line = max(end_line, start_line)
        if start_line > len(source_lines):
            return []
        end_line = min(end_line, len(source_lines))
        return source_lines[start_line - 1 : end_line]

    @staticmethod
    def _normalize_snippet(snippet_lines: List[str]) -> str:
        return "\n".join(line.rstrip() for line in snippet_lines)

    @staticmethod
    def _hash_snippet(snippet: str) -> str:
        return hashlib.sha256(snippet.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_fingerprint(
        rule_id: str,
        file_path: str,
        line: int,
        column: int,
        sink: str,
        source: str,
        code_hash: str,
    ) -> str:
        return f"{rule_id}|{file_path}|{line}|{column}|{sink}|{source}|{code_hash}"

    def _empty_baseline(self) -> BaselineData:
        return BaselineData(
            version="1.0",
            generated_at=self._now_iso(),
            project_root=self.project_root,
            entries=[],
        )

    @staticmethod
    def _now_iso() -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        return timestamp.replace("+00:00", "Z")
