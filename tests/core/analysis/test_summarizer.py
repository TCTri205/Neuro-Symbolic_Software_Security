import ast
from src.core.cfg.builder import CFGBuilder
from src.core.cfg.callgraph import CallGraphBuilder
from src.core.cfg.signature import SignatureExtractor
from src.core.analysis.summarizer import HierarchicalSummarizer


def test_hierarchical_summarization_basic():
    code = """
def leaf_func():
    print("leaf")

def middle_func():
    leaf_func()
    # Direct side effect
    open("log.txt", "w")

def root_func():
    middle_func()
"""
    node = ast.parse(code)
    cfg_builder = CFGBuilder()
    cfg = cfg_builder.build("test_hierarchy", node)

    # We need a CallGraphBuilder that can populate from CFG/AST

    from src.core.cfg.callgraph import CallGraph

    call_graph = CallGraph()
    cg_builder = CallGraphBuilder(call_graph)
    cg_builder.extract_definitions(node)
    cg_builder.build_from_cfg(cfg)

    extractor = SignatureExtractor(cfg)

    summarizer = HierarchicalSummarizer(cg_builder, extractor)

    summaries = summarizer.summarize()

    assert "leaf_func" in summaries
    assert "middle_func" in summaries
    assert "root_func" in summaries

    # leaf_func should have io:print
    leaf_sig = summaries["leaf_func"]
    assert "io:print" in leaf_sig.side_effects

    # middle_func should have io:open AND io:print (propagated from leaf)
    middle_sig = summaries["middle_func"]
    assert "io:open" in middle_sig.side_effects
    assert "io:print" in middle_sig.side_effects

    # root_func should have io:open and io:print (propagated from middle)
    root_sig = summaries["root_func"]
    assert "io:open" in root_sig.side_effects
    assert "io:print" in root_sig.side_effects
