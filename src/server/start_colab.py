import os
import uvicorn
import sys

# Ensure src is in path
sys.path.append(os.getcwd())

from src.server.tunnel import get_public_url


def start():
    """
    Starts the Colab server with Ngrok tunnel.
    """
    print("🚀 Starting NSSS Colab Server...")

    # Set default provider to local if not set
    if not os.getenv("LLM_PROVIDER"):
        os.environ["LLM_PROVIDER"] = "local"
        print("ℹ️  Defaulting LLM_PROVIDER to 'local'")

    port = 8000

    # Start Ngrok
    try:
        print("🔗 Establishing Ngrok tunnel...")
        public_url = get_public_url(port)
        print(f"\n✅ Server accessible at: {public_url}")
        print(f"👉 API Endpoint: {public_url}/analyze")
        print(f"🔑 Ensure your client uses the configured API Key.\n")
    except Exception as e:
        print(f"⚠️  Could not start Ngrok: {e}")
        print("Server will only be available locally.")

    # Start Uvicorn
    print("🔥 Starting Uvicorn...")
    uvicorn.run("src.server.colab_server:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    start()
