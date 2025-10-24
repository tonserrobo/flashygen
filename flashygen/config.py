"""Configuration management for FlashyGen."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    def __init__(self):
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.notion_token = os.getenv("NOTION_TOKEN")
        self.model = "claude-3-haiku-20240307"

        # Adjust cards_per_concept based on model
        # Haiku has lower max_tokens (4096) so we need fewer cards
        if "haiku" in self.model.lower():
            self.cards_per_concept = 2
        else:
            self.cards_per_concept = 5

    def validate(self) -> tuple[bool, str]:
        """Validate that required configuration is present."""
        if not self.anthropic_api_key:
            return False, "ANTHROPIC_API_KEY not found in .env file"
        if not self.notion_token:
            return False, "NOTION_TOKEN not found in .env file"
        return True, "Configuration valid"


def get_config() -> Config:
    """Get application configuration."""
    return Config()
