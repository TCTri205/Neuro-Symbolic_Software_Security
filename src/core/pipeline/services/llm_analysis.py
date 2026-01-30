import ast
import json
from typing import Any, Dict, List, Optional, Type

from src.core.ai.client import LLMClient
from src.core.pipeline.interfaces import (
    GatekeeperPort,
    LLMAnalysisPort,
    LibrarianPort,
    PromptBuilderPort,
)
from src.core.telemetry import MeasureLatency


class LLMAnalysisService(LLMAnalysisPort):
    def __init__(
        self,
        prompt_builder: PromptBuilderPort,
        librarian: LibrarianPort,
        gatekeeper: GatekeeperPort,
        logger,
        client_cls: Type[LLMClient] = LLMClient,
    ) -> None:
        self.prompt_builder = prompt_builder
        self.librarian = librarian
        self.gatekeeper = gatekeeper
        self.logger = logger
        self.client_cls = client_cls

    def analyze(self, cfg, ssa, source: str, file_path: str) -> Optional[str]:
        if not cfg or not ssa:
            return None
        try:
            with MeasureLatency("llm_analysis"):
                self._run_llm_analysis(cfg, ssa, source, file_path)
            return None
        except Exception as e:
            msg = f"LLM analysis failed: {e}"
            self.logger.error(msg)
            return msg

    def _run_llm_analysis(self, cfg, ssa, source: str, file_path: str) -> None:
        provider = self.gatekeeper.preferred_provider()
        client = self.client_cls(provider=provider)
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
            prompt = self.prompt_builder.build_analysis_prompt(
                block, snippet, file_path, ssa_context
            )

            primary_check_id = ""
            if block.security_findings:
                primary_check_id = block.security_findings[0].get("check_id", "")

            cached_insight = self.librarian.query(
                prompt, check_id=primary_check_id, snippet=snippet
            )
            if cached_insight:
                cached_insight["snippet"] = snippet
                block.llm_insights.append(cached_insight)
                continue

            decision = self.gatekeeper.evaluate(prompt=prompt, client=client)
            if not decision.allowed:
                self.logger.info(
                    f"Skipping LLM analysis for {file_path}: {decision.reason}"
                )
                continue

            response = client.chat(prompt)
            self.gatekeeper.record_response(client, response, decision)
            insight = {
                "provider": client.provider,
                "model": client.model,
                "response": response.get("content"),
                "error": response.get("error"),
                "snippet": snippet,
            }

            content = response.get("content")
            if content:
                try:
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
                        analysis = parsed["analysis"]
                        if isinstance(analysis, list):
                            for item in analysis:
                                if not isinstance(item, dict):
                                    continue
                                if "fix_suggestion" not in item and item.get(
                                    "remediation"
                                ):
                                    item["fix_suggestion"] = item.get("remediation")
                                if "remediation" not in item and item.get(
                                    "fix_suggestion"
                                ):
                                    item["remediation"] = item.get("fix_suggestion")
                                if "secure_code_snippet" not in item:
                                    secure_code = item.get("secure_code")
                                    if secure_code:
                                        item["secure_code_snippet"] = secure_code
                            insight["analysis"] = analysis
                except Exception:
                    pass

            if not insight.get("error") and content:
                self.librarian.store(
                    prompt,
                    content,
                    insight.get("analysis", []),
                    client.model,
                    snippet=snippet,
                    check_id=primary_check_id,
                )

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

    def _build_ssa_context(self, block, ssa) -> Dict[str, Any]:
        defs = set()
        uses = set()

        relevant_lines = {
            f.get("line") for f in block.security_findings if f.get("line")
        }
        relevant_vars = set()
        candidates = []

        for stmt in block.statements:
            start = getattr(stmt, "lineno", None)
            end = getattr(stmt, "end_lineno", start)

            is_relevant_stmt = False
            if start is not None and relevant_lines:
                if any(start <= line <= end for line in relevant_lines):
                    is_relevant_stmt = True

            for node in ast.walk(stmt):
                entry = None
                is_def = False

                if isinstance(node, ast.Name):
                    version = ssa.ssa_map.get(node)
                    if not version:
                        continue
                    entry = (node.id, version)
                    if isinstance(node.ctx, ast.Store):
                        is_def = True
                elif isinstance(node, ast.arg):
                    version = ssa.ssa_map.get(node)
                    if not version:
                        continue
                    entry = (node.arg, version)
                    is_def = True

                if entry:
                    if is_relevant_stmt:
                        relevant_vars.add(entry)
                    candidates.append((entry, is_def))

        for entry, is_def in candidates:
            if relevant_vars and entry not in relevant_vars:
                continue

            if is_def:
                defs.add(entry)
            else:
                uses.add(entry)

        phi_nodes = [str(p) for p in block.phi_nodes]
        context = {
            "phi_nodes": phi_nodes,
            "defs": [
                {"name": name, "version": version} for name, version in sorted(defs)
            ],
            "uses": [
                {"name": name, "version": version} for name, version in sorted(uses)
            ],
        }
        return context
