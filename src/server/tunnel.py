import os


def get_public_url(port: int = 8000) -> str:
    """
    Returns the public URL for the server.
    Uses NGROK_URL if present; otherwise tries to start pyngrok.
    """
    env_url = os.getenv("NGROK_URL")
    if env_url:
        return env_url

    try:
        from pyngrok import ngrok
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("pyngrok not installed and NGROK_URL not set") from exc

    tunnel = ngrok.connect(port, "http")
    return tunnel.public_url
