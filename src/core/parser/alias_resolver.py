from __future__ import annotations

from typing import Dict, Iterable, Optional, Set, Tuple

from .ir import IRGraph, IRNode


_SYSTEM_CALL_TARGETS: Set[str] = {
    "os.system",
    "os.popen",
    "subprocess.call",
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.check_output",
}


def resolve_aliased_calls(ir: IRGraph) -> None:
    node_by_id: Dict[str, IRNode] = {node.id: node for node in ir.nodes}
    alias_by_scope: Dict[str, Dict[str, str]] = {}
    known_targets_by_scope: Dict[str, Set[str]] = {}

    for node in ir.nodes:
        scope_id = node.scope_id or "scope:module"
        if node.kind == "Import":
            _record_imports(node, scope_id, alias_by_scope, known_targets_by_scope)
            continue
        if node.kind == "Assign":
            _record_assignment_aliases(
                node,
                scope_id,
                node_by_id,
                alias_by_scope,
                known_targets_by_scope,
            )
            continue
        if node.kind == "Call":
            _resolve_call(node, scope_id, node_by_id, alias_by_scope)


def _record_imports(
    node: IRNode,
    scope_id: str,
    alias_by_scope: Dict[str, Dict[str, str]],
    known_targets_by_scope: Dict[str, Set[str]],
) -> None:
    attrs = node.attrs
    names = attrs.get("names")
    asnames = attrs.get("asnames")
    module = attrs.get("module")
    if not isinstance(names, list) or not isinstance(asnames, list):
        return
    _ensure_scope_maps(scope_id, alias_by_scope, known_targets_by_scope)
    aliases = alias_by_scope[scope_id]
    known_targets = known_targets_by_scope[scope_id]

    if module:
        for name, asname in zip(names, asnames):
            if not isinstance(name, str):
                continue
            target = f"{module}.{name}"
            known_targets.add(target)
            if asname:
                aliases[asname] = target
            else:
                aliases[name] = target
        return

    for name, asname in zip(names, asnames):
        if not isinstance(name, str):
            continue
        known_targets.add(name)
        if asname:
            aliases[asname] = name


def _record_assignment_aliases(
    node: IRNode,
    scope_id: str,
    node_by_id: Dict[str, IRNode],
    alias_by_scope: Dict[str, Dict[str, str]],
    known_targets_by_scope: Dict[str, Set[str]],
) -> None:
    targets: Iterable[Optional[str]] = []
    if isinstance(node.attrs.get("targets"), list):
        targets = node.attrs.get("targets", [])
    elif isinstance(node.attrs.get("target"), str):
        targets = [node.attrs.get("target")]

    value_id = node.attrs.get("value_id")
    if not value_id or value_id not in node_by_id:
        return
    value_node = node_by_id[value_id]
    resolved = _resolve_value_node(
        value_node,
        scope_id,
        node_by_id,
        alias_by_scope,
        known_targets_by_scope,
    )
    if not resolved:
        return

    _ensure_scope_maps(scope_id, alias_by_scope, known_targets_by_scope)
    aliases = alias_by_scope[scope_id]
    known_targets = known_targets_by_scope[scope_id]
    if not _is_known_target(resolved, scope_id, known_targets_by_scope):
        return
    for target in targets:
        if isinstance(target, str) and target:
            aliases[target] = resolved
            known_targets.add(resolved)


def _resolve_value_node(
    node: IRNode,
    scope_id: str,
    node_by_id: Dict[str, IRNode],
    alias_by_scope: Dict[str, Dict[str, str]],
    known_targets_by_scope: Dict[str, Set[str]],
) -> Optional[str]:
    if node.kind == "Name":
        name = node.attrs.get("name")
        if not isinstance(name, str):
            return None
        return _resolve_name(name, scope_id, alias_by_scope, known_targets_by_scope)
    if node.kind == "Attribute":
        return _resolve_attribute_path(
            node, scope_id, node_by_id, alias_by_scope, known_targets_by_scope
        )
    return None


def _resolve_call(
    node: IRNode,
    scope_id: str,
    node_by_id: Dict[str, IRNode],
    alias_by_scope: Dict[str, Dict[str, str]],
) -> None:
    callee_id = node.attrs.get("callee_id")
    if not callee_id or callee_id not in node_by_id:
        return
    callee = node_by_id[callee_id]

    resolved: Optional[str] = None
    alias_used = False
    if callee.kind == "Name":
        name = callee.attrs.get("name")
        if not isinstance(name, str):
            return
        alias = _lookup_alias(name, scope_id, alias_by_scope)
        if alias:
            resolved = alias
            alias_used = True
    elif callee.kind == "Attribute":
        resolved, alias_used = _resolve_attribute_call(
            callee, scope_id, node_by_id, alias_by_scope
        )

    if resolved and resolved in _SYSTEM_CALL_TARGETS:
        node.attrs["resolved_callee"] = resolved
        tags = {"sink"}
        if alias_used:
            tags.add("alias")
        _add_tags(node, tags)


def _resolve_attribute_call(
    callee: IRNode,
    scope_id: str,
    node_by_id: Dict[str, IRNode],
    alias_by_scope: Dict[str, Dict[str, str]],
) -> Tuple[Optional[str], bool]:
    value_id = callee.attrs.get("value_id")
    attr = callee.attrs.get("attr")
    if not value_id or not isinstance(attr, str):
        return None, False
    base_node = node_by_id.get(value_id)
    if not base_node:
        return None, False
    base_path, alias_used = _resolve_attribute_base(
        base_node, scope_id, node_by_id, alias_by_scope
    )
    if not base_path:
        return None, False
    return f"{base_path}.{attr}", alias_used


def _resolve_attribute_path(
    node: IRNode,
    scope_id: str,
    node_by_id: Dict[str, IRNode],
    alias_by_scope: Dict[str, Dict[str, str]],
    known_targets_by_scope: Dict[str, Set[str]],
) -> Optional[str]:
    value_id = node.attrs.get("value_id")
    attr = node.attrs.get("attr")
    if not value_id or not isinstance(attr, str):
        return None
    base_node = node_by_id.get(value_id)
    if not base_node:
        return None
    base_path, _ = _resolve_attribute_base(
        base_node, scope_id, node_by_id, alias_by_scope
    )
    if not base_path:
        return None
    return f"{base_path}.{attr}"


def _resolve_attribute_base(
    node: IRNode,
    scope_id: str,
    node_by_id: Dict[str, IRNode],
    alias_by_scope: Dict[str, Dict[str, str]],
) -> Tuple[Optional[str], bool]:
    if node.kind == "Name":
        name = node.attrs.get("name")
        if not isinstance(name, str):
            return None, False
        alias = _lookup_alias(name, scope_id, alias_by_scope)
        if alias:
            return alias, alias != name
        return name, False
    if node.kind == "Attribute":
        value_id = node.attrs.get("value_id")
        attr = node.attrs.get("attr")
        if not value_id or not isinstance(attr, str):
            return None, False
        base_node = node_by_id.get(value_id)
        if not base_node:
            return None, False
        base_path, alias_used = _resolve_attribute_base(
            base_node, scope_id, node_by_id, alias_by_scope
        )
        if not base_path:
            return None, False
        return f"{base_path}.{attr}", alias_used
    return None, False


def _resolve_name(
    name: str,
    scope_id: str,
    alias_by_scope: Dict[str, Dict[str, str]],
    known_targets_by_scope: Dict[str, Set[str]],
) -> Optional[str]:
    alias = _lookup_alias(name, scope_id, alias_by_scope)
    if alias:
        return alias
    for scope in _scope_chain(scope_id):
        known_targets = known_targets_by_scope.get(scope)
        if known_targets and name in known_targets:
            return name
    return None


def _lookup_alias(
    name: str, scope_id: str, alias_by_scope: Dict[str, Dict[str, str]]
) -> Optional[str]:
    for scope in _scope_chain(scope_id):
        aliases = alias_by_scope.get(scope)
        if aliases and name in aliases:
            return aliases[name]
    return None


def _scope_chain(scope_id: str) -> Iterable[str]:
    if scope_id:
        yield scope_id
    if scope_id != "scope:module":
        yield "scope:module"


def _is_known_target(
    path: str, scope_id: str, known_targets_by_scope: Dict[str, Set[str]]
) -> bool:
    prefixes = _path_prefixes(path)
    for scope in _scope_chain(scope_id):
        known_targets = known_targets_by_scope.get(scope)
        if not known_targets:
            continue
        if any(prefix in known_targets for prefix in prefixes):
            return True
    return False


def _path_prefixes(path: str) -> Iterable[str]:
    parts = path.split(".")
    for idx in range(1, len(parts) + 1):
        yield ".".join(parts[:idx])


def _ensure_scope_maps(
    scope_id: str,
    alias_by_scope: Dict[str, Dict[str, str]],
    known_targets_by_scope: Dict[str, Set[str]],
) -> None:
    alias_by_scope.setdefault(scope_id, {})
    known_targets_by_scope.setdefault(scope_id, set())


def _add_tags(node: IRNode, tags: Iterable[str]) -> None:
    existing = node.attrs.get("tags")
    if not isinstance(existing, list):
        existing = []
    for tag in tags:
        if tag not in existing:
            existing.append(tag)
    node.attrs["tags"] = existing
