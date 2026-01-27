import os
import time
from fastapi import FastAPI, Header, HTTPException
from src.core.ai.client import LLMClient
from src.core.ai.gateway import LLMGatewayService
from src.core.ai.protocol import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisData,
    ConstraintCheck,
)


app = FastAPI()


def _require_api_key(x_api_key: str | None) -> None:
    expected = os.getenv("NSSS_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/analyze", response_model=AnalysisResponse)
def analyze(
    request: AnalysisRequest, x_api_key: str | None = Header(None)
) -> AnalysisResponse:
    _require_api_key(x_api_key)

    start_time = time.time()

    system_prompt = "You are a software security expert. Respond succinctly."
    user_prompt = request.function_signature

    client = LLMClient()
    gateway = LLMGatewayService(client=client)

    try:
        response_text = gateway.analyze(system_prompt, user_prompt)
    except Exception as exc:
        return AnalysisResponse(
            status="error",
            error_code="LLM_FAILURE",
            message=str(exc),
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    data = AnalysisData(
        is_vulnerable=False,
        confidence_score=0.0,
        risk_level="SAFE",
        reasoning_trace="",
        analysis_summary=response_text,
        fix_suggestion=None,
        secure_code_snippet=None,
        constraint_check=ConstraintCheck(syntax_valid=True, logic_sound=True),
    )

    return AnalysisResponse(
        status="success",
        data=data,
        processing_time_ms=(time.time() - start_time) * 1000,
    )
