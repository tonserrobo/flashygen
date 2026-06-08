"""Configuration management for FlashyGen."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    def __init__(self, provider: str = "ollama"):
        """Initialize configuration.

        Args:
            provider: Either "ollama" (default) or "claude" for proprietary model
        """
        self.provider = provider.lower()
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.notion_token = os.getenv("NOTION_TOKEN")

        # Ollama configuration
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("FG_OLLAMA_MODEL") or os.getenv("OLLAMA_MODEL", "gemma3:4b")

        # Set model based on provider
        if self.provider == "claude":
            self.model = "claude-haiku-4-5-20251001"
        else:
            self.model = self.ollama_model

        self.cards_per_concept = 3

    def validate(self) -> tuple[bool, str]:
        """Validate that required configuration is present."""
        # Claude API key only required when using Claude
        if self.provider == "claude" and not self.anthropic_api_key:
            return False, "ANTHROPIC_API_KEY not found in .env file (required for Claude provider)"
        if not self.notion_token:
            return False, "NOTION_TOKEN not found in .env file"
        return True, "Configuration valid"


def get_config(provider: str = "ollama") -> Config:
    """Get application configuration.

    Args:
        provider: Either "ollama" (default) or "claude" for proprietary model
    """
    return Config(provider)
