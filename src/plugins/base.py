from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING
from src.core.context.loader import ProjectContext

if TYPE_CHECKING:
    from src.core.pipeline.events import PipelineEventRegistry


@dataclass
class Route:
    path: str
    method: str  # GET, POST, etc.
    handler: str  # Function/Class name or reference
    metadata: dict = field(default_factory=dict)  # Extra info like auth required, etc.


class FrameworkPlugin(ABC):
    """
    Abstract base class for framework-specific plugins (Django, Flask, FastAPI).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the plugin (e.g., 'django', 'flask')."""
        pass

    @abstractmethod
    def detect(self, context: ProjectContext) -> bool:
        """
        Determine if the project uses this framework based on context
        (e.g., dependencies in pyproject/requirements, settings).
        """
        pass

    @abstractmethod
    def parse_routes(self, project_path: str) -> List[Route]:
        """
        Extract routes from the project code.
        """
        pass


class PipelineEventPlugin(ABC):
    """
    Abstract base class for plugins that register pipeline event handlers.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the plugin."""
        pass

    @abstractmethod
    def register(self, registry: "PipelineEventRegistry") -> None:
        """Register handlers in the provided pipeline event registry."""
        pass
