from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    FALSE_POSITIVE = "FALSE_POSITIVE"
    TRUE_POSITIVE = "TRUE_POSITIVE"
    ADJUST_RISK = "ADJUST_RISK"
    IGNORE = "IGNORE"


class FeedbackItem(BaseModel):
    id: str  # Signature hash
    feedback_type: FeedbackType
    adjusted_score: Optional[float] = None
    comment: Optional[str] = None
    user_id: str = "system"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FeedbackRequest(BaseModel):
    check_id: str
    metadata: dict
    feedback_type: FeedbackType
    comment: Optional[str] = None
    adjusted_score: Optional[float] = None
