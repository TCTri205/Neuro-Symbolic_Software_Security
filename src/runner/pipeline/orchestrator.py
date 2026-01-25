import os
import ast
import json
from typing import Dict, Any, List, Optional
from src.core.cfg.builder import CFGBuilder
from src.core.cfg.ssa.transformer import SSATransformer
from src.core.cfg.callgraph import CallGraph, CallGraphBuilder
from src.runner.tools.semgrep import SemgrepRunner
from src.runner.tools.llm import LLMClient

class Pipeline:
    def __init__(self):
        self.results = {}

    def scan_file(self, file_path: str):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source, filename=file_path)
            
            # Initialize Call Graph components
            call_graph = CallGraph()
            cg_builder = CallGraphBuilder(call_graph)
            
            # Phase 1: Extract definitions for Speculative Expansion
            cg_builder.extract_definitions(tree)
            
            builder = CFGBuilder()
            # Build CFG for the whole module
            cfg = builder.build(os.path.basename(file_path), tree)

            semgrep_runner = SemgrepRunner()
            semgrep_results = semgrep_runner.run(file_path)
            self._map_semgrep_findings(cfg, semgrep_results, file_path)
            
            # Phase 2: Build Call Graph from CFG
            cg_builder.build_from_cfg(cfg)
            
            ssa = SSATransformer(cfg)
            ssa.analyze()

            self._run_llm_analysis(cfg, ssa, source, file_path)
            
            self.results[file_path] = self._serialize(cfg, ssa, call_graph, semgrep_results)
            
        except Exception as e:
            self.results[file_path] = {"error": str(e)}

    def _serialize(self, cfg, ssa, cg, semgrep_results: Dict[str, Any]) -> Dict[str, Any]:
        blocks = []
        for block in cfg._blocks.values():
            # Simply count statements for summary
            # and list phis
            phis = [str(p) for p in block.phi_nodes]
            blocks.append({
                "id": block.id,
                "scope": block.scope,
                "stmt_count": len(block.statements),
                "phis": phis,
                "security_findings": block.security_findings,
                "llm_insights": block.llm_insights
            })
            
        edges = []
        for u, v, data in cfg.graph.edges(data=True):
            edges.append({
                "source": u, 
                "target": v, 
                "label": data.get("label")
            })
            
        # Serialize Call Graph
        cg_nodes = []
        for n, data in cg.graph.nodes(data=True):
            cg_nodes.append({"id": n, "kind": data.get("kind")})
            
        cg_edges = []
        for u, v, data in cg.graph.edges(data=True):
            cg_edges.append({"source": u, "target": v, "type": data.get("type")})
            
        return {
            "name": cfg.name,
            "stats": {
                "block_count": len(cfg._blocks),
                "edge_count": len(cfg.graph.edges),
                "var_count": len(ssa.vars),
                "cg_node_count": len(cg.graph.nodes),
                "cg_edge_count": len(cg.graph.edges)
            },
            "structure": {
                "blocks": blocks,
                "edges": edges
            },
            "call_graph": {
                "nodes": cg_nodes,
                "edges": cg_edges
            },
            "semgrep": semgrep_results
        }

    def _run_llm_analysis(self, cfg, ssa, source: str, file_path: str):
        client = LLMClient()
        if not client.is_configured:
            return

        source_lines = source.splitlines()
        for block in cfg._blocks.values():
            if not block.security_findings:
                continue

            snippet = self._extract_block_source(block, source_lines)
            if not snippet:
                continue

            ssa_context = self._build_ssa_context(block, ssa)
            prompt = self._build_llm_prompt(block, snippet, file_path, ssa_context)
            response = client.chat(prompt)
            insight = {
                "provider": client.provider,
                "model": client.model,
                "response": response.get("content"),
                "error": response.get("error"),
            }
            
            # Attempt to parse JSON from content
            content = response.get("content")
            if content:
                try:
                    # Strip markdown code blocks
                    clean_content = content.strip()
                    if clean_content.startswith("```json"):
                        clean_content = clean_content[7:]
                    elif clean_content.startswith("```"):
                        clean_content = clean_content[3:]
                    
                    if clean_content.endswith("```"):
                        clean_content = clean_content[:-3]
                    
                    clean_content = clean_content.strip()
                    
                    parsed = json.loads(clean_content)
                    if isinstance(parsed, dict) and "analysis" in parsed:
                        insight["analysis"] = parsed["analysis"]
                except Exception:
                    # Failed to parse, valid JSON might not be returned
                    pass

            if "status" in response:
                insight["status"] = response["status"]
            if "body" in response:
                insight["body"] = response["body"]
            if "raw" in response:
                insight["raw"] = response["raw"]
            block.llm_insights.append(insight)

    def _extract_block_source(self, block, source_lines: List[str]) -> str:
        min_line = None
        max_line = None
        for stmt in block.statements:
            start = getattr(stmt, "lineno", None)
            if start is None:
                continue
            end = getattr(stmt, "end_lineno", start)
            if min_line is None or start < min_line:
                min_line = start
            if max_line is None or end > max_line:
                max_line = end

        if min_line is None or max_line is None:
            return ""

        min_line = max(min_line, 1)
        max_line = min(max_line, len(source_lines))
        return "\n".join(source_lines[min_line - 1 : max_line])

    def _build_llm_prompt(
        self,
        block,
        snippet: str,
        file_path: str,
        ssa_context: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        findings = json.dumps(block.security_findings, indent=2)
        ssa_summary = json.dumps(ssa_context, indent=2)
        message = (
            "You are a security analyst. For each finding, determine whether it is a true positive, "
            "false positive, or needs review. Provide a concise rationale and a specific code remediation.\n"
            "Respond in JSON with an array under key 'analysis', each item containing 'check_id', "
            "'verdict', 'rationale', and 'remediation'.\n\n"
            f"File: {file_path}\n"
            f"Block scope: {block.scope}\n"
            f"Block id: {block.id}\n\n"
            "SSA context:\n"
            f"{ssa_summary}\n\n"
            "Findings:\n"
            f"{findings}\n\n"
            "Code snippet:\n"
            f"{snippet}"
        )
        return [
            {"role": "system", "content": "You analyze code security findings."},
            {"role": "user", "content": message},
        ]

    def _map_semgrep_findings(self, cfg, semgrep_results: Dict[str, Any], file_path: str):
        findings = semgrep_results.get("results", [])
        if not findings:
            return

        target_path = os.path.abspath(file_path)
        unmapped = semgrep_results.setdefault("unmapped", [])

        for finding in findings:
            finding_path = finding.get("path")
            if finding_path:
                if os.path.abspath(finding_path) != target_path:
                    if not target_path.endswith(finding_path):
                        continue

            start = finding.get("start", {})
            line = start.get("line")
            if not line:
                unmapped.append(finding)
                continue

            block = self._find_block_by_line(cfg, line)
            if not block:
                unmapped.append(finding)
                continue

            finding_info = {
                "check_id": finding.get("check_id"),
                "message": finding.get("extra", {}).get("message"),
                "severity": finding.get("extra", {}).get("severity"),
                "line": line,
                "column": start.get("col"),
            }
            block.security_findings.append(finding_info)

    def _build_ssa_context(self, block, ssa) -> Dict[str, Any]:
        defs = set()
        uses = set()
        
        # Filter for variables involved in the findings
        relevant_lines = {f.get("line") for f in block.security_findings if f.get("line")}
        relevant_vars = set()

        if relevant_lines:
            for stmt in block.statements:
                start = getattr(stmt, "lineno", None)
                if start is None:
                    continue
                end = getattr(stmt, "end_lineno", start)
                
                # Check if statement overlaps with any finding line
                if any(start <= line <= end for line in relevant_lines):
                    for node in ast.walk(stmt):
                        if isinstance(node, ast.Name):
                            version = ssa.ssa_map.get(node)
                            if version:
                                relevant_vars.add((node.id, version))
                        elif isinstance(node, ast.arg):
                            version = ssa.ssa_map.get(node)
                            if version:
                                relevant_vars.add((node.arg, version))

        for stmt in block.statements:
            for node in ast.walk(stmt):
                if isinstance(node, ast.Name):
                    version = ssa.ssa_map.get(node)
                    if not version:
                        continue
                    
                    entry = (node.id, version)
                    # Filter: Only include if relevant (or if no relevant vars found, fallback to all?)
                    # Let's strict filter if relevant_vars is populated.
                    if relevant_vars and entry not in relevant_vars:
                        continue
                        
                    if isinstance(node.ctx, ast.Store):
                        defs.add(entry)
                    else:
                        uses.add(entry)
                elif isinstance(node, ast.arg):
                    version = ssa.ssa_map.get(node)
                    if version:
                        entry = (node.arg, version)
                        if relevant_vars and entry not in relevant_vars:
                            continue
                        defs.add(entry)

        phi_nodes = [str(p) for p in block.phi_nodes]
        context = {
            "phi_nodes": phi_nodes,
            "defs": [{"name": name, "version": version} for name, version in sorted(defs)],
            "uses": [{"name": name, "version": version} for name, version in sorted(uses)],
        }
        return context

    def _find_block_by_line(self, cfg, line: int) -> Optional[Any]:
        for block in cfg._blocks.values():
            for stmt in block.statements:
                start = getattr(stmt, "lineno", None)
                if start is None:
                    continue
                end = getattr(stmt, "end_lineno", start)
                if start <= line <= end:
                    return block
        return None

    def scan_directory(self, dir_path: str):
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    self.scan_file(full_path)

def run_scan_pipeline(target: str) -> Dict[str, Any]:
    pipeline = Pipeline()
    if os.path.isfile(target):
        pipeline.scan_file(target)
    elif os.path.isdir(target):
        pipeline.scan_directory(target)
    return pipeline.results
