from fastapi.testclient import TestClient
from src.server import colab_server


def _payload():
    return {
        "function_signature": "def foo(): pass",
        "language": "python",
        "vulnerability_type": "sqli",
        "context": {"source_variable": "x", "line_number": 1},
        "privacy_mask": {"enabled": True, "map": {}},
        "metadata": {"mode": "precision", "request_id": "req-1"},
    }


def test_api_key_middleware_rejects(monkeypatch):
    monkeypatch.setenv("NSSS_API_KEY", "secret")
    client = TestClient(colab_server.app)
    response = client.post("/analyze", json=_payload())
    assert response.status_code == 401


def test_api_key_middleware_accepts(monkeypatch):
    monkeypatch.setenv("NSSS_API_KEY", "secret")
    monkeypatch.setattr(
        colab_server.LLMGatewayService,
        "analyze",
        lambda self, system_prompt, user_prompt: "ok",
    )
    client = TestClient(colab_server.app)
    response = client.post("/analyze", json=_payload(), headers={"X-API-Key": "secret"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
