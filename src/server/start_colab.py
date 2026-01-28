import os
import uvicorn
import sys
import signal
from pyngrok import ngrok

# Ensure src is in path
sys.path.append(os.getcwd())

from src.server.tunnel import get_public_url


def handle_shutdown(signum, frame):
    print("\n🛑 Shutting down server...")
    print("🧹 Cleaning up Ngrok tunnels...")
    ngrok.kill()
    sys.exit(0)


def start():
    """
    Starts the Colab server with Ngrok tunnel.
    """
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("🚀 Starting NSSS Colab Server...")

    # Set default provider to local if not set
    if not os.getenv("LLM_PROVIDER"):
        os.environ["LLM_PROVIDER"] = "local"
        print("ℹ️  Defaulting LLM_PROVIDER to 'local'")

    port = 8000

    # Configure Ngrok Auth
    auth_token = os.getenv("NGROK_AUTHTOKEN")
    if auth_token:
        print("🔐 Configuring Ngrok with provided token.")
        ngrok.set_auth_token(auth_token)
    else:
        print("⚠️  No NGROK_AUTHTOKEN found. Tunnel might expire quickly.")

    # Start Ngrok
    try:
        print("🔗 Establishing Ngrok tunnel...")
        # Kill any existing tunnels first
        ngrok.kill()

        public_url = get_public_url(port)
        print(f"\n✅ Server accessible at: {public_url}")
        print(f"👉 API Endpoint: {public_url}/analyze")
        print(f"👉 Health Check: {public_url}/health")
        print("🔑 Ensure your client uses the configured API Key.\n")
    except Exception as e:
        print(f"⚠️  Could not start Ngrok: {e}")
        print("Server will only be available locally.")

    # Start Uvicorn
    print("🔥 Starting Uvicorn...")
    uvicorn.run("src.server.colab_server:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    start()
