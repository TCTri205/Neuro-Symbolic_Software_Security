import pytest
from src.core.ai.guard import AntiHallucinationGuard


def test_guard_allows_clean_text():
    guard = AntiHallucinationGuard()
    guard.validate("Use existing functions only.")


def test_guard_blocks_imports():
    guard = AntiHallucinationGuard()
    with pytest.raises(ValueError, match="import"):
        guard.validate("Please import requests and try again.")
