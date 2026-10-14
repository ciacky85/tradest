"""
app/config.py - Gestione centralizzata delle configurazioni.

Carica variabili d'ambiente da .env e fornisce un oggetto Settings
validato tramite Pydantic Settings per tutta l'applicazione.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Percorso base del progetto (root workspace)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"


class Settings(BaseSettings):
    """Configurazione globale dell'applicazione, caricata da .env."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Applicazione ---
    app_name: str = "AI-Trading-Bot"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    app_log_level: str = "DEBUG"

    # --- Google Gemini AI ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"
    gemini_max_tokens: int = 4096
    gemini_temperature: float = 0.3

    # --- Interactive Brokers ---
    ibkr_host: str = "192.168.1.212"
    ibkr_port: int = 4004
    ibkr_client_id: int = 500
    ibkr_account_id: str = ""
    ibkr_timeout: int = 30

    # --- Database ---
    database_url: str = f"sqlite:///{DATA_DIR / 'trading.db'}"
    database_echo: bool = False

    # --- Notifiche ---
    notify_webhook_url: str = "http://192.168.1.212:9008/notify"
    notify_enabled: bool = True
    notify_timeout: int = 10

    # --- Trading ---
    trading_enabled: bool = False
    trading_mode: Literal["paper", "live"] = "paper"
    max_daily_loss: float = 500.0
    emergency_stop_loss: float = 1000.0
    ai_min_confidence: float = 0.70

    # --- Scheduling ---
    analysis_interval_seconds: int = 30
    portfolio_sync_interval_seconds: int = 60

    # --- Timezone ---
    timezone: str = "Europe/Rome"

    # --- Validatori ---
    @field_validator("app_log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"Log level deve essere uno di {allowed}")
        return upper

    @field_validator("ai_min_confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("ai_min_confidence deve essere tra 0.0 e 1.0")
        return v

    # --- Proprietà derivate ---
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_debug(self) -> bool:
        return self.app_debug and not self.is_production


# ---------------------------------------------------------------------------
# Singleton settings - importabile ovunque
# ---------------------------------------------------------------------------
_settings: Settings | None = None


def get_settings() -> Settings:
    """Restituisce l'istanza singleton delle impostazioni."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Forza il reload delle impostazioni (utile per test)."""
    global _settings
    _settings = Settings()
    return _settings


# ---------------------------------------------------------------------------
# Caricamento file JSON di configurazione
# ---------------------------------------------------------------------------
def load_trading_params() -> dict:
    """Carica i parametri di trading da config/trading_params.json."""
    path = CONFIG_DIR / "trading_params.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_ai_prompts() -> dict:
    """Carica i template prompt AI da config/ai_prompts.json."""
    path = CONFIG_DIR / "ai_prompts.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_symbols_config() -> dict:
    """Carica la configurazione dei simboli da config/symbols.json."""
    path = CONFIG_DIR / "symbols.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)
