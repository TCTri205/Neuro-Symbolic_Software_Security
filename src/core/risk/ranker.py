from typing import Dict, List, Optional

from src.core.risk.schema import (
    RankerOutput,
    RiskLevel,
    RiskScore,
    RiskScoreItem,
    RiskSignal,
)
from src.core.taint.engine import TaintFlow

DEFAULT_SOURCE_SENSITIVITY: Dict[str, float] = {
    "secret": 1.0,
    "password": 1.0,
    "token": 0.95,
    "key": 0.9,
    "credential": 0.9,
    "private": 0.85,
    "ssn": 1.0,
    "credit": 1.0,
    "card": 1.0,
    "pii": 0.8,
}

DEFAULT_SINK_SENSITIVITY: Dict[str, float] = {
    "exec": 1.0,
    "eval": 1.0,
    "system": 1.0,
    "subprocess": 0.95,
    "pickle": 0.85,
    "yaml.load": 0.85,
    "sql": 0.8,
    "query": 0.75,
    "open": 0.6,
    "write": 0.6,
    "send": 0.6,
    "http": 0.6,
    "request": 0.6,
    "print": 0.4,
    "sink": 0.4,
}

DEFAULT_SIGNAL_WEIGHTS: Dict[str, float] = {
    "source_sensitivity": 0.35,
    "sink_sensitivity": 0.25,
    "path_length": 0.25,
    "implicit_flow": 0.15,
}

MAX_PATH_LENGTH = 7


class RankerService:
    def __init__(
        self,
        source_sensitivity: Optional[Dict[str, float]] = None,
        sink_sensitivity: Optional[Dict[str, float]] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.source_sensitivity = source_sensitivity or DEFAULT_SOURCE_SENSITIVITY
        self.sink_sensitivity = sink_sensitivity or DEFAULT_SINK_SENSITIVITY
        self.weights = self._normalize_weights(weights or DEFAULT_SIGNAL_WEIGHTS)

    def rank(self, flows: List[TaintFlow]) -> RankerOutput:
        items: List[RiskScoreItem] = []
        for flow in flows:
            items.append(self._score_flow(flow))

        overall = self._compute_overall(items)
        return RankerOutput(items=items, overall=overall)

    def _score_flow(self, flow: TaintFlow) -> RiskScoreItem:
        path_length = len(flow.path) if flow.path else 1
        source_score = self._match_sensitivity(flow.source, self.source_sensitivity)
        sink_score = self._match_sensitivity(flow.sink, self.sink_sensitivity)
        path_score = self._score_path_length(path_length)
        implicit_score = 1.0 if flow.implicit else 0.0

        signals = [
            RiskSignal(
                name="source_sensitivity",
                weight=self.weights["source_sensitivity"],
                score=source_score,
                rationale=f"Matched source '{flow.source}'.",
            ),
            RiskSignal(
                name="sink_sensitivity",
                weight=self.weights["sink_sensitivity"],
                score=sink_score,
                rationale=f"Matched sink '{flow.sink}'.",
            ),
            RiskSignal(
                name="path_length",
                weight=self.weights["path_length"],
                score=path_score,
                rationale=f"Path length {path_length}.",
            ),
            RiskSignal(
                name="implicit_flow",
                weight=self.weights["implicit_flow"],
                score=implicit_score,
                rationale="Implicit flow detected."
                if flow.implicit
                else "Explicit flow.",
            ),
        ]

        weighted_score = sum(signal.weight * signal.score for signal in signals)
        risk_score = round(weighted_score * 100.0, 2)
        confidence = self._score_confidence(path_length, flow.implicit)
        risk_level = self._risk_level(risk_score)

        risk = RiskScore(
            risk_level=risk_level,
            risk_score=risk_score,
            confidence=confidence,
            is_vulnerable=risk_score >= 50.0,
            summary=f"{flow.source} -> {flow.sink}",
        )

        metadata = {
            "source": flow.source,
            "sink": flow.sink,
            "path": flow.path,
            "path_length": path_length,
            "implicit": flow.implicit,
        }

        return RiskScoreItem(
            check_id="TAINT_FLOW", risk=risk, signals=signals, metadata=metadata
        )

    def _score_path_length(self, path_length: int) -> float:
        if path_length <= 2:
            return 1.0
        if path_length >= MAX_PATH_LENGTH:
            return 0.1
        decay = (path_length - 2) / (MAX_PATH_LENGTH - 2)
        return max(0.1, 1.0 - decay)

    def _score_confidence(self, path_length: int, implicit: bool) -> float:
        base = 0.6
        length_bonus = min(0.25, 0.05 * path_length)
        implicit_bonus = 0.05 if implicit else 0.0
        return min(1.0, base + length_bonus + implicit_bonus)

    def _match_sensitivity(self, value: str, mapping: Dict[str, float]) -> float:
        value_lower = value.lower()
        best_score = 0.3
        for key, score in mapping.items():
            if key in value_lower:
                best_score = max(best_score, score)
        return best_score

    def _risk_level(self, score: float) -> RiskLevel:
        if score >= 85.0:
            return RiskLevel.CRITICAL
        if score >= 70.0:
            return RiskLevel.HIGH
        if score >= 50.0:
            return RiskLevel.MEDIUM
        if score >= 30.0:
            return RiskLevel.LOW
        return RiskLevel.SAFE

    def _compute_overall(self, items: List[RiskScoreItem]) -> Optional[RiskScore]:
        if not items:
            return None

        top_item = max(items, key=lambda item: item.risk.risk_score)
        return RiskScore(
            risk_level=top_item.risk.risk_level,
            risk_score=top_item.risk.risk_score,
            confidence=top_item.risk.confidence,
            is_vulnerable=top_item.risk.is_vulnerable,
            summary="Highest risk taint flow.",
        )

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        total = sum(weights.values())
        if total <= 0:
            return dict(DEFAULT_SIGNAL_WEIGHTS)
        return {key: value / total for key, value in weights.items()}
