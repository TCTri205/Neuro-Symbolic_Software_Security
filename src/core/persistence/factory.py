import os
from typing import Dict, Optional

from src.core.persistence.graph_serializer import GraphPersistenceService
from src.core.persistence.interfaces import GraphPersistenceManagerPort

_GRAPH_PERSISTENCE: Optional[GraphPersistenceManagerPort] = None
_GRAPH_PERSISTENCE_BY_ROOT: Dict[str, GraphPersistenceManagerPort] = {}


def get_graph_persistence_service(
    project_root: Optional[str] = None,
) -> GraphPersistenceManagerPort:
    if _GRAPH_PERSISTENCE is not None:
        return _GRAPH_PERSISTENCE

    if project_root is None:
        return GraphPersistenceService.get_instance()

    root = os.path.abspath(project_root)
    if root not in _GRAPH_PERSISTENCE_BY_ROOT:
        _GRAPH_PERSISTENCE_BY_ROOT[root] = GraphPersistenceService()
    return _GRAPH_PERSISTENCE_BY_ROOT[root]


def set_graph_persistence_service(service: GraphPersistenceManagerPort) -> None:
    global _GRAPH_PERSISTENCE
    _GRAPH_PERSISTENCE = service


def clear_graph_persistence_cache() -> None:
    """Clear all cached persistence instances. For testing only."""
    global _GRAPH_PERSISTENCE_BY_ROOT
    _GRAPH_PERSISTENCE_BY_ROOT.clear()
