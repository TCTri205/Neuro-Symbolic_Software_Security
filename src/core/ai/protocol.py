from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field

# ---------------------------------------------------------
# Request Schema (Laptop -> Colab)
# ---------------------------------------------------------


class AnalysisContext(BaseModel):
    source_variable: Optional[str] = None
    sink_function: Optional[str] = None
    line_number: Optional[int] = None
    file_path: Optional[str] = None
    sanitizers_found: List[str] = Field(default_factory=list)


class PrivacyMaskConfig(BaseModel):
    enabled: bool = True
    map: Dict[str, str] = Field(default_factory=dict)


class RequestMetadata(BaseModel):
    mode: Literal["precision", "recall"] = "precision"
    request_id: str


class AnalysisRequest(BaseModel):
    function_signature: str
    language: str = "python"
    vulnerability_type: str
    context: AnalysisContext
    privacy_mask: PrivacyMaskConfig
    metadata: RequestMetadata


# ---------------------------------------------------------
# Response Schema (Colab -> Laptop)
# ---------------------------------------------------------


class ConstraintCheck(BaseModel):
    syntax_valid: bool
    logic_sound: bool


class AnalysisData(BaseModel):
    is_vulnerable: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "SAFE"]
    reasoning_trace: str
    analysis_summary: str
    fix_suggestion: Optional[str] = None
    secure_code_snippet: Optional[str] = None
    constraint_check: Optional[ConstraintCheck] = None


class AnalysisResponse(BaseModel):
    status: Literal["success", "error"]
    data: Optional[AnalysisData] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    processing_time_ms: Optional[float] = None
