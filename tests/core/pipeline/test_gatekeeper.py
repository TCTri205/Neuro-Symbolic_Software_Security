from src.core.pipeline.gatekeeper import BudgetConfiguration, GatekeeperService


class DummyClient:
    def __init__(
        self,
        provider: str = "gemini",
        model: str = "gemini-1.5-flash",
        is_configured: bool = True,
    ) -> None:
        self.provider = provider
        self.model = model
        self.is_configured = is_configured


def test_gatekeeper_blocks_when_provider_unconfigured():
    gatekeeper = GatekeeperService()
    client = DummyClient(is_configured=False)

    decision = gatekeeper.evaluate(prompt="test", client=client)

    assert decision.allowed is False
    assert "not configured" in decision.reason.lower()


def test_gatekeeper_blocks_when_over_token_budget():
    config = BudgetConfiguration(max_tokens_per_scan=5, max_completion_tokens=0)
    gatekeeper = GatekeeperService(config)
    client = DummyClient()

    decision = gatekeeper.evaluate(prompt="x" * 100, client=client)

    assert decision.allowed is False
    assert "token budget" in decision.reason.lower()


def test_gatekeeper_blocks_during_rate_limit_cooldown():
    gatekeeper = GatekeeperService()
    client = DummyClient()

    gatekeeper.record_rate_limit(client.provider)
    decision = gatekeeper.evaluate(prompt="test", client=client)

    assert decision.allowed is False
    assert "rate limit" in decision.reason.lower()
