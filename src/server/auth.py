import os
from fastapi.responses import JSONResponse


class APIKeyMiddleware:
    """Simple API key middleware using the X-API-Key header."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        expected = os.getenv("NSSS_API_KEY")
        if expected:
            headers = dict(scope.get("headers", []))
            provided = headers.get(b"x-api-key")
            if provided is None or provided.decode("utf-8") != expected:
                response = JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": "Unauthorized"},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
