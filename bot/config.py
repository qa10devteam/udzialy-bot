"""
Bot configuration via Pydantic Settings.

Loads configuration from config.yaml with environment variable overrides
(prefix: UDZIALY_).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- Sub-models ---

class TelegramConfig(BaseModel):
    """Telegram bot settings."""
    token: str = "YOUR_BOT_TOKEN_HERE"
    owner_id: int = 0


class PortalEntry(BaseModel):
    """Single portal configuration."""
    enabled: bool = True
    base_url: str = ""


class PortalsConfig(BaseModel):
    """All portal switches."""
    otodom: PortalEntry = PortalEntry()
    olx: PortalEntry = PortalEntry()
    gratka: PortalEntry = PortalEntry()
    morizon: PortalEntry = PortalEntry()
    nieruchomosci_online: PortalEntry = PortalEntry()
    domiporta: PortalEntry = PortalEntry()
    lento: PortalEntry = PortalEntry()
    gethome: PortalEntry = PortalEntry()
    ogloszenia24: PortalEntry = PortalEntry(enabled=False)

    def enabled_portals(self) -> list[str]:
        """Return list of enabled portal names."""
        return [
            name for name, entry in self.__dict__.items()
            if isinstance(entry, PortalEntry) and entry.enabled
        ]


class ScrapingConfig(BaseModel):
    """Scraping behavior settings."""
    timeout: int = 30
    max_concurrent: int = 3
    retry_count: int = 2
    retry_delay: int = 5
    delay_between: int = 2
    user_agent_rotate: bool = True


class TorConfig(BaseModel):
    """Tor proxy settings."""
    enabled: bool = True
    socks_port: int = 9050
    control_port: int = 9051
    control_password: str = "udzialy_tor_pass"
    circuit_rotate_interval: int = 300
    binary_path: str = "tor/tor.exe"

    @property
    def proxy_url(self) -> str:
        """SOCKS5 proxy URL for httpx."""
        return f"socks5://127.0.0.1:{self.socks_port}"


class DatabaseConfig(BaseModel):
    """Database settings."""
    path: str = "data/udzialy.db"


class LoggingConfig(BaseModel):
    """Logging settings."""
    level: str = "INFO"
    file: str = "data/bot.log"


# --- Main Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from config.yaml + environment variables.

    Environment variables override YAML values with prefix UDZIALY_.
    Example: UDZIALY_TELEGRAM__TOKEN=xxx overrides telegram.token.
    """

    model_config = SettingsConfigDict(
        env_prefix="UDZIALY_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    telegram: TelegramConfig = TelegramConfig()
    portals: PortalsConfig = PortalsConfig()
    scraping: ScrapingConfig = ScrapingConfig()
    tor: TorConfig = TorConfig()
    database: DatabaseConfig = DatabaseConfig()
    logging: LoggingConfig = LoggingConfig()

    @classmethod
    def from_yaml(cls, path: str | Path = "config.yaml") -> "Settings":
        """Load settings from YAML file, then apply env var overrides."""
        config_path = Path(path)
        yaml_data: dict[str, Any] = {}

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}

        return cls(**yaml_data)


# --- Singleton ---

_settings: Settings | None = None


def get_settings(config_path: str | Path = "config.yaml") -> Settings:
    """Get or create settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings.from_yaml(config_path)
    return _settings
