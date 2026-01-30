from dataclasses import dataclass
from typing import List, Optional

from src.core.analysis.sanitizers import SanitizerRegistry
from src.core.taint.engine import TaintConfiguration, TaintSink, TaintSource


DEFAULT_TAINT_SOURCES = [
    "input",
    "os.getenv",
    "getenv",
    "request.args.get",
    "request.form.get",
    "request.get_json",
]

DEFAULT_TAINT_SINKS = [
    "exec",
    "eval",
    "os.system",
    "subprocess.run",
    "subprocess.call",
    "open",
    "print",
]


@dataclass(frozen=True)
class PipelineConfig:
    enable_ir: bool = False
    enable_docstring_stripping: bool = False
    baseline_mode: bool = False
    semgrep_config: Optional[str] = None
    taint_config: Optional[TaintConfiguration] = None
    taint_sources: Optional[List[str]] = None
    taint_sinks: Optional[List[str]] = None


def build_taint_config(config: PipelineConfig) -> TaintConfiguration:
    if config.taint_config:
        return config.taint_config

    sources = config.taint_sources or DEFAULT_TAINT_SOURCES
    sinks = config.taint_sinks or DEFAULT_TAINT_SINKS
    return TaintConfiguration(
        sources=[TaintSource(name=source) for source in sources],
        sinks=[TaintSink(name=sink) for sink in sinks],
        sanitizers=list(SanitizerRegistry._DEFAULT_MAPPING.keys()),
    )
