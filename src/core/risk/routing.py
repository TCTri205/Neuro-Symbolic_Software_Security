from typing import Iterable, Optional, Set

from src.core.risk.schema import (
    RankerOutput,
    RiskLevel,
    RiskScore,
    RiskScoreItem,
    RoutingDecision,
    RoutingPlan,
    RoutingTarget,
)


DEFAULT_LLM_LEVELS = {RiskLevel.CRITICAL, RiskLevel.HIGH}


class RoutingService:
    def __init__(self, llm_levels: Optional[Iterable[RiskLevel]] = None) -> None:
        if llm_levels is None:
            self.llm_levels: Set[RiskLevel] = set(DEFAULT_LLM_LEVELS)
        else:
            self.llm_levels = set(llm_levels)

    def route(self, output: RankerOutput) -> RoutingPlan:
        items = [self._route_item(item) for item in output.items]
        overall = None
        if output.overall is not None:
            overall = self._decision(output.overall)
        return RoutingPlan(items=items, overall=overall)

    def _route_item(self, item: RiskScoreItem) -> RoutingDecision:
        decision = self._decision(item.risk, check_id=item.check_id)
        return decision

    def _decision(
        self, risk: RiskScore, check_id: Optional[str] = None
    ) -> RoutingDecision:
        target = (
            RoutingTarget.LLM
            if risk.risk_level in self.llm_levels
            else RoutingTarget.RULES
        )
        rationale = (
            "High-risk finding; route to LLM."
            if target == RoutingTarget.LLM
            else "Low-risk finding; keep rule-based handling."
        )
        return RoutingDecision(
            target=target,
            risk_level=risk.risk_level,
            risk_score=risk.risk_score,
            confidence=risk.confidence,
            check_id=check_id,
            rationale=rationale,
        )
