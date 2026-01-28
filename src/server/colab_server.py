import re
import time
import json
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from src.core.ai.client import LLMClient, AIClientFactory
from src.core.ai.gateway import LLMGatewayService
from src.core.ai.protocol import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisData,
    ConstraintCheck,
)
from src.server.auth import APIKeyMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("colab_server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager to handle startup and shutdown events.
    Ensures the heavy ML model is loaded exactly once when the server starts.
    """
    provider = os.getenv("LLM_PROVIDER", "mock")  # Default to mock for safety
    logger.info(f"🚀 Initializing Server with Provider: {provider}")

    # Initialize Client (Singleton via Factory)
    client = AIClientFactory.get_client(provider=provider)

    # Pre-load model weights into GPU memory if applicable
    if hasattr(client, "load_model"):
        logger.info(f"⏳ Loading model resources for {provider}...")
        try:
            client.load_model()
            logger.info("✅ Model loaded successfully!")
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            # We don't crash here, allowing server to start, but requests might fail

    yield

    logger.info("🛑 Server shutting down...")


app = FastAPI(lifespan=lifespan)
app.add_middleware(APIKeyMiddleware)


@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    provider = os.getenv("LLM_PROVIDER", "mock")
    client = AIClientFactory.get_client(provider=provider)

    status = "healthy"
    model_loaded = False

    if provider == "local":
        if hasattr(client, "engine") and client.engine.model is not None:
            model_loaded = True
        else:
            status = "loading"  # Or degraded

    return {"status": status, "provider": provider, "model_loaded": model_loaded}


def extract_json_payload(text: str) -> str:
    """Robustly extract JSON object from text using regex."""
    # Pattern to find the last valid JSON-like block enclosed in braces
    # Non-greedy match for content inside braces, allowing for nested structure is hard with regex,
    # but for LLM output, usually we look for the outermost braces.
    # We'll try to find the substring starting with { and ending with }

    text = text.strip()

    # 1. Try to find markdown block first
    markdown_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if markdown_match:
        return markdown_match.group(1)

    markdown_match_simple = re.search(r"```\s*(\{.*?\})\s*```", text, re.DOTALL)
    if markdown_match_simple:
        return markdown_match_simple.group(1)

    # 2. Fallback: Search for the first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    # 3. If no braces, return original text (will fail parsing)
    return text


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    start_time = time.time()
    req_id = request.metadata.request_id if request.metadata else "unknown"
    logger.info(f"[{req_id}] Received analysis request")

    # Construct strict JSON Prompt (Sync with DataFactory.process_row)
    # The Model was trained to expect:
    # Instruction: "Analyze the following Python code trace for {vuln_type} vulnerabilities. Return logic in JSON."
    # Input: JSON String { function_signature, vulnerability_type, context }

    vuln_type = request.vulnerability_type or "Security Vulnerability"

    system_prompt = f"Analyze the following Python code trace for {vuln_type} vulnerabilities. Return logic in JSON."

    # Construct input object matching Training Schema (DataFactory)
    input_payload = {
        "function_signature": request.function_signature,
        "vulnerability_type": vuln_type,
        "context": request.context.model_dump()
        if request.context
        else {"sanitizers_found": []},
    }

    user_prompt = json.dumps(input_payload, indent=2)

    # Resolve provider again (in case env var changed, though usually static)
    provider = os.getenv("LLM_PROVIDER", "mock")

    # Get the cached client instance
    client = AIClientFactory.get_client(provider=provider)
    gateway = LLMGatewayService(client=client)

    try:
        # Run inference in a separate thread to avoid blocking the Event Loop
        # This is CRITICAL for high throughput
        response_text = await run_in_threadpool(
            gateway.analyze, system_prompt, user_prompt
        )
    except Exception as exc:
        logger.error(f"[{req_id}] LLM Failure: {exc}")
        return AnalysisResponse(
            status="error",
            error_code="LLM_FAILURE",
            message=str(exc),
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    try:
        # Clean response (remove markdown code blocks if present)
        from src.core.ai.cot import extract_cot

        # Remove thinking process first
        clean_text, _ = extract_cot(response_text)

        # Robust extraction
        json_text = extract_json_payload(clean_text)

        parsed_json = json.loads(json_text)

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
        logger.info(f"[{req_id}] Analysis success. Vuln: {data.is_vulnerable}")

    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        logger.warning(
            f"[{req_id}] JSON Parse Error: {e}. Raw response: {response_text[:100]}..."
        )
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
