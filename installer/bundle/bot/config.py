"""
Bot configuration — loads config.yaml relative to project root.

Exposes a Settings dataclass with: telegram_token, owner_id, portals dict,
tor config, scraping timeouts. Uses pydantic-settings with YAML source.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- Project root detection ---

def _find_project_root() -> Path:
    """Find project root by looking for config.yaml upward from this file."""
    current = Path(__file__).resolve().parent  # bot/
    for parent in [current.parent, current.parent.parent, Path.cwd()]:
        if (parent / "config.yaml").exists():
            return parent
    # Fallback: assume CWD is project root
    return Path.cwd()


PROJECT_ROOT = _find_project_root()


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
    """All portal switches — dynamic dict of portal entries."""
    model_config = {"extra": "allow"}

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
        result = []
        for name in self.model_fields:
            entry = getattr(self, name, None)
            if isinstance(entry, PortalEntry) and entry.enabled:
                result.append(name)
        return result

    def as_dict(self) -> Dict[str, Dict[str, Any]]:
        """Return portals as plain dict."""
        result = {}
        for name in self.model_fields:
            entry = getattr(self, name, None)
            if isinstance(entry, PortalEntry):
                result[name] = {"enabled": entry.enabled, "base_url": entry.base_url}
        return result


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
    control_password: str = "udzialy2026"
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

    # Convenience properties
    @property
    def telegram_token(self) -> str:
        return self.telegram.token

    @property
    def owner_id(self) -> int:
        return self.telegram.owner_id

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> "Settings":
        """Load settings from YAML file, then apply env var overrides."""
        if path is None:
            path = PROJECT_ROOT / "config.yaml"
        config_path = Path(path)
        yaml_data: dict[str, Any] = {}

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}

        return cls(**yaml_data)


# --- Singleton ---

_settings: Settings | None = None


def get_settings(config_path: str | Path | None = None) -> Settings:
    """Get or create settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings.from_yaml(config_path)
    return _settings


def reset_settings() -> None:
    """Reset singleton (for testing)."""
    global _settings
    _settings = None
