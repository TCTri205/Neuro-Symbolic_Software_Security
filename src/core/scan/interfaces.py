from typing import Protocol


class GraphProjectPersistencePort(Protocol):
    def load_project_graph(self, project_root: str, strict: bool = True): ...


class ProcessRunnerPort(Protocol):
    def __call__(self, *args, **kwargs): ...
