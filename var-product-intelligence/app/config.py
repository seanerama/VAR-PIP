"""Application configuration using Pydantic settings."""

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load .env file into os.environ so API_KEY_* vars are accessible
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite:///./var_products.db"

    # Anthropic API
    anthropic_api_key: str = ""

    # PDF Output
    pdf_output_dir: str = "./output"
    pdf_expiry_hours: int = 24

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars like API_KEY_*

    def get_api_keys(self) -> dict[str, str]:
        """Get all API keys from environment variables.

        Returns a dict mapping username to API key.
        Environment variables should be in format: API_KEY_{USERNAME}=key
        """
        api_keys = {}
        for key, value in os.environ.items():
            if key.startswith("API_KEY_"):
                username = key[8:].lower()  # Remove "API_KEY_" prefix
                api_keys[value] = username
        return api_keys


settings = Settings()
