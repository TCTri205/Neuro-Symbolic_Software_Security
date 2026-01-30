from typing import Any, Dict, Optional, Tuple

from src.core.parser import PythonAstParser
from src.core.persistence import GraphPersistenceService
from src.core.pipeline.interfaces import GraphPersistencePort, IRPort
from src.core.telemetry import MeasureLatency


class IRService(IRPort):
    def __init__(
        self,
        enable_ir: bool,
        enable_docstring_stripping: bool,
        logger,
        persistence: Optional[GraphPersistencePort] = None,
    ) -> None:
        self.enable_ir = enable_ir
        self.enable_docstring_stripping = enable_docstring_stripping
        self.logger = logger
        self.persistence = persistence or GraphPersistenceService.get_instance()

    def build_ir(
        self, source_code: str, file_path: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not self.enable_ir:
            return None, None

        try:
            cached_graph = None
            if file_path and file_path != "<unknown>":
                cached_graph = self.persistence.load_ir_graph_for_file(
                    file_path, strict=True
                )

            if cached_graph:
                ir_graph, _meta = cached_graph
                return ir_graph.model_dump(by_alias=True), None

            with MeasureLatency("parse_ir"):
                parser = PythonAstParser(
                    source_code,
                    file_path,
                    enable_docstring_stripping=self.enable_docstring_stripping,
                )
                ir_graph = parser.parse()
                ir_payload = ir_graph.model_dump(by_alias=True)

            if file_path and file_path != "<unknown>":
                try:
                    self.persistence.save_ir_graph(ir_graph, file_path)
                except Exception as e:
                    self.logger.error(f"Graph persistence failed: {e}")

            return ir_payload, None
        except Exception as e:
            msg = f"IR parsing failed: {e}"
            self.logger.error(msg)
            return None, msg
