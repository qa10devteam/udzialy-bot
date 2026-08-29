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
    """Find project root by looking for config.yaml in standard locations."""
    import os
    
    # 1. Environment variable (set by CLI)
    env_config = os.environ.get("UDZIALY_CONFIG")
    if env_config and Path(env_config).exists():
        return Path(env_config).parent
    
    # 2. User home directory (~/.udzialy-bot/)
    home_config = Path.home() / ".udzialy-bot"
    if (home_config / "config.yaml").exists():
        return home_config
    
    # 3. Relative to this file (development mode)
    current = Path(__file__).resolve().parent  # bot/
    for parent in [current.parent, current.parent.parent]:
        if (parent / "config.yaml").exists():
            return parent
    
    # 4. CWD
    if (Path.cwd() / "config.yaml").exists():
        return Path.cwd()
    
    # Fallback: user home config dir (will be created by setup)
    return home_config


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
    # Whole-portal budget (all keywords x pages). Browser-driven portals (Otodom)
    # need ~50s, OLX via Tor ~45s. Must be well above `timeout` (single request).
    portal_timeout: int = 90
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


# --- LLM model defaults (single source of truth for setup, AI chat and analysis) ---

# Claude default: Sonnet 4.6. Exact Anthropic model ID — no date suffix.
CLAUDE_DEFAULT_MODEL = "claude-sonnet-4-6"

DEFAULT_LLM_MODELS: Dict[str, str] = {
    "claude": CLAUDE_DEFAULT_MODEL,
    "anthropic": CLAUDE_DEFAULT_MODEL,
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "deepseek": "deepseek-chat",
    "ollama": "llama3",
}

# Models that earlier versions wrote into config.yaml as the *default* for Claude.
# A config still carrying one of these gets the current default at load time.
SUPERSEDED_CLAUDE_DEFAULTS = {"claude-haiku-4-5-20251001", "claude-haiku-4-5"}


def default_model_for(provider: str) -> str:
    """Default model ID for a provider name as used in config.yaml."""
    return DEFAULT_LLM_MODELS.get((provider or "openai").lower(), "gpt-4o-mini")


def normalize_llm_model(provider: str, model: str | None) -> str:
    """Resolve empty/superseded defaults to the current default for the provider."""
    prov = (provider or "openai").lower()
    if prov in ("claude", "anthropic") and (not model or model in SUPERSEDED_CLAUDE_DEFAULTS):
        return CLAUDE_DEFAULT_MODEL
    return model or default_model_for(prov)


class LLMConfig(BaseModel):
    """LLM analysis settings (optional)."""
    enabled: bool = False
    provider: str = "openai"  # openai, claude/anthropic, gemini, deepseek, ollama
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    max_concurrent: int = 5
    timeout: int = 15


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
        extra="ignore",
    )

    telegram: TelegramConfig = TelegramConfig()

    def __init__(self, **data):
        # Strip whitespace from token (copy-paste artifact)
        if "telegram" in data and isinstance(data["telegram"], dict):
            if "token" in data["telegram"]:
                data["telegram"]["token"] = str(data["telegram"]["token"]).strip()
        super().__init__(**data)
        # Resolve empty / superseded default model IDs (e.g. configs written by
        # older `udzialy setup` with the previous Claude default).
        self.llm.model = normalize_llm_model(self.llm.provider, self.llm.model)
    portals: PortalsConfig = PortalsConfig()
    scraping: ScrapingConfig = ScrapingConfig()
    tor: TorConfig = TorConfig()
    database: DatabaseConfig = DatabaseConfig()
    llm: LLMConfig = LLMConfig()
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
            try:
                with open(config_path, "rb") as fb:
                    raw = fb.read()
                # Strip BOM if present (Notepad on Windows adds it)
                if raw.startswith(b"\xef\xbb\xbf"):
                    raw = raw[3:]
                loaded = yaml.safe_load(raw.decode("utf-8"))
                yaml_data = loaded if isinstance(loaded, dict) else {}
            except yaml.YAMLError as e:
                import logging
                logging.getLogger(__name__).error(f"Config YAML parse error: {e}. Using defaults.")
                yaml_data = {}

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
