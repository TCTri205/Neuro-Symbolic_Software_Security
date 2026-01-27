from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    SAFE = "SAFE"
    UNKNOWN = "UNKNOWN"


class RiskSignal(BaseModel):
    name: str
    weight: float = Field(..., ge=0.0, le=1.0)
    score: float = Field(..., ge=0.0, le=1.0)
    rationale: Optional[str] = None


class RiskScore(BaseModel):
    risk_level: RiskLevel
    risk_score: float = Field(..., ge=0.0, le=100.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_vulnerable: bool
    summary: Optional[str] = None


class RiskScoreItem(BaseModel):
    check_id: str
    path: Optional[str] = None
    line: Optional[int] = Field(default=None, ge=1)
    column: Optional[int] = Field(default=None, ge=1)
    category: Optional[str] = None
    severity: Optional[str] = None
    risk: RiskScore
    signals: List[RiskSignal] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RankerOutput(BaseModel):
    version: str = "1.0"
    items: List[RiskScoreItem] = Field(default_factory=list)
    overall: Optional[RiskScore] = None
