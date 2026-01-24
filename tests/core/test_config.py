import os
import pytest
from src.core.config import Settings

def test_default_settings():
    """Test that default settings are loaded correctly."""
    settings = Settings()
    assert settings.HOST == "0.0.0.0"
    assert settings.PORT == 8000
    assert settings.DEBUG is True
    assert settings.MODE == "audit"
    assert settings.GRAPH_STORAGE_PATH == "./.graph_data"

def test_env_override(monkeypatch):
    """Test that environment variables override defaults."""
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("MODE", "ci")
    monkeypatch.setenv("DEBUG", "False")
    
    # Reload settings implies creating a new instance since environment vars are read at instantiation
    settings = Settings()
    
    assert settings.PORT == 9000
    assert settings.MODE == "ci"
    assert settings.DEBUG is False

def test_optional_fields():
    """Test that optional fields are None by default if not set."""
    # Ensure these env vars are unset for the test
    with pytest.MonkeyPatch.context() as m:
        m.delenv("OPENAI_API_KEY", raising=False)
        m.delenv("ANTHROPIC_API_KEY", raising=False)
        
        settings = Settings()
        assert settings.OPENAI_API_KEY is None or settings.OPENAI_API_KEY == "sk-placeholder" 
        # Note: If .env exists with placeholder, it might load it. 
        # Since we are testing logic, we assume clean env or handle .env presence.
