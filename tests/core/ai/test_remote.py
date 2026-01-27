import pytest
from src.core.ai.remote import RemoteAIClient


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


def test_remote_client_success(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return DummyResponse(
            payload={"status": "success", "data": {"analysis_summary": "ok"}}
        )

    monkeypatch.setattr("requests.post", fake_post)
    client = RemoteAIClient(base_url="http://server")
    assert client.analyze("sys", "user") == "ok"


def test_remote_client_error(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return DummyResponse(payload={"status": "error", "message": "bad"})

    monkeypatch.setattr("requests.post", fake_post)
    client = RemoteAIClient(base_url="http://server")
    with pytest.raises(RuntimeError, match="bad"):
        client.analyze("sys", "user")
