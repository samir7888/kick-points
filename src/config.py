"""Configuration management."""

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Application configuration."""

    channels: list[str]
    messages: list[str]
    authorization: str
    wait_times: dict[str, int | dict[str, int]]
    web_dashboard: Optional[dict] = field(default=None)
    prediction: Optional[dict] = field(default=None)
    telegram: Optional[dict] = field(default=None)

    @classmethod
    def load(cls, path: str = "config.json") -> "Config":
        """Load configuration from JSON file or CONFIG_JSON environment variable."""
        import os
        if os.environ.get("CONFIG_JSON"):
            data = json.loads(os.environ["CONFIG_JSON"])
            return cls(**data)

        if not os.path.exists(path) and os.path.exists("config.example.json"):
            # If config.json doesn't exist, check if environment variables are set
            pass

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
