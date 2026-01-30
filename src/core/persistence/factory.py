from typing import Optional

from src.core.persistence.graph_serializer import GraphPersistenceService
from src.core.persistence.interfaces import GraphPersistenceManagerPort

_GRAPH_PERSISTENCE: Optional[GraphPersistenceManagerPort] = None


def get_graph_persistence_service() -> GraphPersistenceManagerPort:
    return _GRAPH_PERSISTENCE or GraphPersistenceService.get_instance()


def set_graph_persistence_service(service: GraphPersistenceManagerPort) -> None:
    global _GRAPH_PERSISTENCE
    _GRAPH_PERSISTENCE = service
