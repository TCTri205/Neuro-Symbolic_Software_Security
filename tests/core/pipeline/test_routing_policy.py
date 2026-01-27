from src.core.pipeline.orchestrator import AnalysisOrchestrator
from src.core.risk.schema import RoutingTarget
from src.core.taint.engine import TaintConfiguration, TaintSink, TaintSource


def test_orchestrator_adds_routing_plan():
    code = """
secret_token = secret_source()
exec(secret_token)
"""
    config = TaintConfiguration(
        sources=[TaintSource(name="secret_source")],
        sinks=[TaintSink(name="exec")],
    )
    orchestrator = AnalysisOrchestrator(taint_config=config)
    result = orchestrator.analyze_code(code, "routing.py")

    assert result.ranker_output is not None
    assert result.routing is not None
    assert result.routing.overall is not None
    assert result.routing.overall.target == RoutingTarget.LLM
