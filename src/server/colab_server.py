import time
import json
from fastapi import FastAPI
from src.core.ai.client import LLMClient
from src.core.ai.gateway import LLMGatewayService
from src.core.ai.protocol import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisData,
    ConstraintCheck,
)
from src.server.auth import APIKeyMiddleware


app = FastAPI()
app.add_middleware(APIKeyMiddleware)


@app.post("/analyze", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    start_time = time.time()

    system_prompt = "You are a software security expert. Respond succinctly."
    user_prompt = request.function_signature

    # Determine provider from environment or default to "local" for Colab
    # In a real deployment, this would be set via env var LLM_PROVIDER
    import os

    provider = os.getenv(
        "LLM_PROVIDER", "mock"
    )  # Default to mock for safety if not set

    # Use Factory to get the appropriate client
    from src.core.ai.client import AIClientFactory

    client = AIClientFactory.get_client(provider=provider)

    # If using local client, ensure model is loaded
    if provider == "local" and hasattr(client, "load_model"):
        client.load_model()

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

    try:
        parsed_json = json.loads(response_text)
        if not isinstance(parsed_json, dict):
            raise ValueError("Response is not a JSON object")

        data = AnalysisData(
            is_vulnerable=parsed_json.get("is_vulnerable", False),
            confidence_score=parsed_json.get("confidence_score", 0.0),
            risk_level=parsed_json.get("risk_level", "SAFE"),
            reasoning_trace=parsed_json.get("reasoning_trace", ""),
            analysis_summary=parsed_json.get(
                "analysis_summary", str(parsed_json)
            ),  # Fallback to full dump if missing
            fix_suggestion=parsed_json.get("fix_suggestion"),
            secure_code_snippet=parsed_json.get("secure_code_snippet"),
            constraint_check=parsed_json.get("constraint_check"),
        )
    except (json.JSONDecodeError, AttributeError):
        # Fallback if response is not JSON (e.g. raw text from base model or Mock)
        data = AnalysisData(
            is_vulnerable=False,
            confidence_score=0.0,
            risk_level="SAFE",
            reasoning_trace="Response format was text, not JSON.",
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
