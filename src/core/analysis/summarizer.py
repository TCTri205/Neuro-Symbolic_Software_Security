from typing import Dict
from src.core.cfg.callgraph import CallGraphBuilder
from src.core.cfg.signature import SignatureExtractor, FunctionSignature


class HierarchicalSummarizer:
    def __init__(
        self,
        call_graph_builder: CallGraphBuilder,
        signature_extractor: SignatureExtractor,
    ):
        self.cg_builder = call_graph_builder
        self.sig_extractor = signature_extractor
        self.summaries: Dict[str, FunctionSignature] = {}

    def summarize(self) -> Dict[str, FunctionSignature]:
        """
        Performs hierarchical summarization starting from leaf nodes.
        Returns a dictionary mapping function names to their signatures (summaries).
        """
        # 1. Build Call Graph to get dependencies
        # Assuming the CG is already built or we trigger it.
        # For this implementation, let's assume we can access the underlying graph structure from cg_builder.

        # Access the CallGraph object inside the builder
        graph = self.cg_builder.cg.graph
        if not graph:
            return {}

        # Topological sort (or reverse topological for processing leaves first?
        # Actually, if A calls B, we want B summarized before A.
        # So we want post-order traversal or reverse topological sort of the dependency graph.
        # NetworkX topological_sort returns nodes in dependency order (if A -> B, A comes before B?? No).
        # In a Call Graph: A -> B means A calls B. B is a dependency of A.
        # Standard topological sort on (u, v) edges gives u before v.
        # So if A -> B, A comes before B.
        # We want to process B first. So we need reverse topological sort.

        import networkx as nx

        try:
            # Reverse the list from topological sort
            processing_order = list(reversed(list(nx.topological_sort(graph))))
        except nx.NetworkXUnfeasible:
            # Graph has cycles. Handle cycles (recursion).
            # For now, just break cycles or process in arbitrary valid order, or use strongly connected components.
            # Fallback: simple list
            processing_order = list(graph.nodes())

        signatures = {sig.name: sig for sig in self.sig_extractor.extract()}

        # 2. Process in order
        for func_name in processing_order:
            if func_name not in signatures:
                continue

            sig = signatures[func_name]

            # Enriched signature with callee info
            # "Bubbling up": We might want to propagate side-effects or taint from callees to caller.
            # This is where the "Summarization" happens.

            callees = list(graph.successors(func_name))
            for callee in callees:
                if callee in self.summaries:
                    callee_sig = self.summaries[callee]
                    # Propagate side-effects
                    for effect in callee_sig.side_effects:
                        # Add if not present (maybe prefix with "callee:"?)
                        # For now, just propagate raw to show dependencies
                        if effect not in sig.side_effects:
                            sig.side_effects.append(effect)

                    # Propagate taint sinks/sources (simplified)
                    for sink in callee_sig.taint_sinks:
                        if sink not in sig.taint_sinks:
                            sig.taint_sinks.append(sink)

            # Save the enriched signature
            self.summaries[func_name] = sig

        return self.summaries
