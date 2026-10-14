"""
app/config.py - Gestione centralizzata delle configurazioni.

Carica variabili d'ambiente da .env e supporta una cartella di configurazione
esterna persistente (TRADEST_CONF_DIR) con auto-provisioning dei file di default.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Percorsi di Base e Directory di Configurazione Esterna
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# Se è specificata TRADEST_CONF_DIR nell'ambiente (es. per Portainer / Docker mount),
# usiamo quella cartella esterna per configurazioni, DB SQLite e logs.
# Altrimenti fallback locale sul workspace di sviluppo.
_env_conf_dir = os.environ.get("TRADEST_CONF_DIR")

if _env_conf_dir:
    CONF_STORAGE_DIR = Path(_env_conf_dir)
else:
    CONF_STORAGE_DIR = BASE_DIR / "config"

DEFAULT_TEMPLATES_DIR = BASE_DIR / "config"
DATA_STORAGE_DIR = (
    Path(_env_conf_dir) if _env_conf_dir else (BASE_DIR / "data")
)
LOGS_DIR = (
    (Path(_env_conf_dir) / "logs") if _env_conf_dir else (BASE_DIR / "logs")
)


def ensure_conf_files_exist() -> None:
    """
    Assicura che la directory di configurazione esterna esista
    e che i file template JSON siano copiati se non già presenti.
    """
    CONF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    json_files = ["trading_params.json", "ai_prompts.json", "symbols.json"]
    for jf in json_files:
        dest = CONF_STORAGE_DIR / jf
        src = DEFAULT_TEMPLATES_DIR / jf
        if not dest.exists() and src.exists():
            try:
                shutil.copy2(src, dest)
            except Exception:
                pass


# Inizializza i file al primo caricamento del modulo
ensure_conf_files_exist()


class Settings(BaseSettings):
    """Configurazione globale dell'applicazione, caricata da .env o env vars."""

    model_config = SettingsConfigDict(
        env_file=str(CONF_STORAGE_DIR / ".env") if (CONF_STORAGE_DIR / ".env").exists() else str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Applicazione ---
    app_name: str = "Tradest-AI-Bot"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    app_log_level: str = "INFO"

    # --- Google Gemini AI ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"
    gemini_max_tokens: int = 4096
    gemini_temperature: float = 0.2

    # --- Interactive Brokers ---
    ibkr_host: str = "192.168.1.212"
    ibkr_port: int = 4004
    ibkr_client_id: int = 500
    ibkr_account_id: str = ""
    ibkr_timeout: int = 30

    # --- Database ---
    database_url: str = f"sqlite:///{DATA_STORAGE_DIR / 'trading.db'}"
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

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_debug(self) -> bool:
        return self.app_debug and not self.is_production


# ---------------------------------------------------------------------------
# Singleton settings
# ---------------------------------------------------------------------------
_settings: Settings | None = None


def get_settings() -> Settings:
    """Restituisce l'istanza singleton delle impostazioni."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Forza il reload delle impostazioni."""
    global _settings
    _settings = Settings()
    return _settings


# ---------------------------------------------------------------------------
# Caricamento file JSON di configurazione
# ---------------------------------------------------------------------------
def _load_json_with_fallback(filename: str) -> dict:
    dest = CONF_STORAGE_DIR / filename
    src = DEFAULT_TEMPLATES_DIR / filename
    target = dest if dest.exists() else src
    with open(target, encoding="utf-8") as f:
        return json.load(f)


def load_trading_params() -> dict:
    """Carica i parametri di trading."""
    return _load_json_with_fallback("trading_params.json")


def load_ai_prompts() -> dict:
    """Carica i template prompt AI."""
    return _load_json_with_fallback("ai_prompts.json")


def load_symbols_config() -> dict:
    """Carica la configurazione dei simboli."""
    return _load_json_with_fallback("symbols.json")
