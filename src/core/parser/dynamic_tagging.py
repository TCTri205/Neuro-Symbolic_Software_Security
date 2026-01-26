from __future__ import annotations

from typing import Dict, Iterable, Set

from .ir import IRGraph, IRNode


_DYNAMIC_CALLEE_NAMES: Set[str] = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "getattr",
    "setattr",
}

_DYNAMIC_ATTR_NAMES: Set[str] = {
    "import_module",
}


def tag_dynamic_areas(ir: IRGraph) -> None:
    node_by_id: Dict[str, IRNode] = {node.id: node for node in ir.nodes}
    for node in ir.nodes:
        if node.attrs.get("unsupported") is True:
            _add_tags(node, {"dynamic", "unscannable"})
            continue

        if node.kind != "Call":
            continue

        callee_id = node.attrs.get("callee_id")
        if not callee_id or callee_id not in node_by_id:
            _add_tags(node, {"dynamic", "unscannable"})
            continue

        callee = node_by_id[callee_id]
        if callee.kind not in {"Name", "Attribute"}:
            _add_tags(node, {"dynamic", "unscannable"})
            continue

        if callee.kind == "Name":
            name = callee.attrs.get("name")
            if name in _DYNAMIC_CALLEE_NAMES:
                _add_tags(node, {"dynamic", "unscannable"})
                continue

        if callee.kind == "Attribute":
            attr = callee.attrs.get("attr")
            if attr in _DYNAMIC_ATTR_NAMES:
                _add_tags(node, {"dynamic", "unscannable"})
                continue

        if _has_dynamic_kwargs(node):
            _add_tags(node, {"dynamic"})


def _has_dynamic_kwargs(node: IRNode) -> bool:
    keywords = node.attrs.get("keywords")
    if not isinstance(keywords, list):
        return False
    return any(kw.get("name") is None for kw in keywords if isinstance(kw, dict))


def _add_tags(node: IRNode, tags: Iterable[str]) -> None:
    existing = node.attrs.get("tags")
    if not isinstance(existing, list):
        existing = []
    for tag in tags:
        if tag not in existing:
            existing.append(tag)
    node.attrs["tags"] = existing
