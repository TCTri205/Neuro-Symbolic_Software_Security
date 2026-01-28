#!/bin/bash
# Setup script for Google Colab environment
# Usage: source scripts/setup_colab.sh

set -e

echo "📦 Installing NSSS dependencies..."
pip install -r requirements.txt

echo "🧠 Installing Unsloth and AI dependencies..."
# Unsloth installation for Colab (keeps updating, using standard recommendation)
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
pip install --no-deps "xformers<0.0.27" "trl<0.9.0" peft accelerate bitsandbytes

echo "🌐 Installing Server dependencies..."
pip install pyngrok uvicorn

echo "✅ Setup complete!"
echo ""
echo "To start the server:"
echo "  export NGROK_AUTHTOKEN=your_token_here (Optional but recommended)"
echo "  python -m src.server.start_colab"
