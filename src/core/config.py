from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # API Configuration
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API Key")
    ANTHROPIC_API_KEY: Optional[str] = Field(None, description="Anthropic API Key")
    NGROK_AUTH_TOKEN: Optional[str] = Field(None, description="Ngrok Auth Token")

    # Server Configuration
    HOST: str = Field("0.0.0.0", description="Server Host")
    PORT: int = Field(8000, description="Server Port")
    DEBUG: bool = Field(True, description="Debug Mode")
    MODE: str = Field("audit", description="Operation Mode: ci, audit, baseline")

    # Database / Graph
    GRAPH_STORAGE_PATH: str = Field("./.graph_data", description="Path to store graph data")

    # AI Server
    AI_SERVER_URL: str = Field("http://localhost:8000", description="Centralized AI Server URL")
    AI_CLIENT_SECRET: Optional[str] = Field(None, description="Secret key for AI Server authentication")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()
