from src.server.tunnel import get_public_url


def test_get_public_url_env(monkeypatch):
    monkeypatch.setenv("NGROK_URL", "https://example.ngrok.io")
    assert get_public_url() == "https://example.ngrok.io"
