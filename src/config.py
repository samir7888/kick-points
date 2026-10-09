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
        """Load configuration from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
