import pytest
from pydantic import ValidationError

from src.core.risk.schema import RankerOutput, RiskLevel, RiskScore, RiskScoreItem


def test_risk_score_accepts_valid_values():
    score = RiskScore(
        risk_level=RiskLevel.HIGH,
        risk_score=82.5,
        confidence=0.91,
        is_vulnerable=True,
        summary="High confidence injection path.",
    )
    assert score.risk_level == RiskLevel.HIGH
    assert score.risk_score == 82.5
    assert score.confidence == 0.91


def test_risk_score_rejects_out_of_range_values():
    with pytest.raises(ValidationError):
        RiskScore(
            risk_level=RiskLevel.MEDIUM,
            risk_score=120.0,
            confidence=0.5,
            is_vulnerable=True,
        )

    with pytest.raises(ValidationError):
        RiskScore(
            risk_level=RiskLevel.LOW,
            risk_score=30.0,
            confidence=1.2,
            is_vulnerable=False,
        )


def test_risk_score_item_defaults_and_validation():
    item = RiskScoreItem(
        check_id="CWE-89",
        risk=RiskScore(
            risk_level=RiskLevel.CRITICAL,
            risk_score=95.0,
            confidence=0.98,
            is_vulnerable=True,
        ),
    )
    assert item.signals == []
    assert item.metadata == {}

    with pytest.raises(ValidationError):
        RiskScoreItem(
            check_id="CWE-78",
            line=0,
            risk=RiskScore(
                risk_level=RiskLevel.HIGH,
                risk_score=80.0,
                confidence=0.9,
                is_vulnerable=True,
            ),
        )


def test_ranker_output_defaults():
    output = RankerOutput()
    assert output.version == "1.0"
    assert output.items == []
    assert output.overall is None
