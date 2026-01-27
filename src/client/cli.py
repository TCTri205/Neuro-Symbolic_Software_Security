import argparse
import sys
import logging
from src.core.ai.client import AIClientFactory
from src.core.ai.gateway import LLMGatewayService


def main() -> None:
    parser = argparse.ArgumentParser(description="NSSS AI Client CLI")
    parser.add_argument("--prompt", help="User prompt to send", required=True)
    parser.add_argument(
        "--system", help="System prompt", default="You are a security expert."
    )
    parser.add_argument(
        "--provider", help="AI Provider (openai, gemini, mock)", default="mock"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    try:
        client = AIClientFactory.get_client(provider=args.provider)
        gateway = LLMGatewayService(client=client)

        print(f"Sending prompt to {args.provider}...")
        response = gateway.analyze(args.system, args.prompt)
        print("\nResponse:")
        print(response)

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
