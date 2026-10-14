"""
app/main.py - Entry point dell'applicazione FastAPI AI Trading Bot.

Fornisce:
- Lifespan handler per startup e shutdown asincrono
- Endpoint di health check e diagnostica
- Endpoint per consultare portfolio, ordini e trade
- Endpoint per controllo manuale del bot (start/stop/pause)
- Endpoint per consultare le decisioni AI
- Documentazione Swagger/OpenAPI interattiva
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import (
    get_settings,
    load_ai_prompts,
    load_symbols_config,
    load_trading_params,
)
from app.models import HealthResponse, StatusResponse
from data.database import Database, get_db
from utils.logger import get_logger, setup_logging

# Timestamp di avvio applicazione per il calcolo dell'uptime
_START_TIME = time.time()

logger = get_logger("app.main")


# ---------------------------------------------------------------------------
# Lifespan context manager (sostituisce i vecchi startup/shutdown events)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestisce il ciclo di vita dell'applicazione: startup e shutdown."""
    # --- STARTUP ---
    setup_logging()
    settings = get_settings()
    logger.info(
        "Avvio AI Trading Bot",
        version=__version__,
        env=settings.app_env,
        debug=settings.app_debug,
        port=settings.app_port,
    )

    # Inizializza il database SQLite
    db = get_db()
    try:
        await db.connect()
        logger.info("Database inizializzato con successo")
    except Exception as exc:
        logger.error("Errore inizializzazione database", error=str(exc))

    yield

    # --- SHUTDOWN ---
    logger.info("Arresto AI Trading Bot in corso...")
    try:
        await db.disconnect()
        logger.info("Database disconnesso correttamente")
    except Exception as exc:
        logger.error("Errore durante disconnessione database", error=str(exc))
    logger.info("AI Trading Bot arrestato")


# ---------------------------------------------------------------------------
# Creazione dell'applicazione FastAPI
# ---------------------------------------------------------------------------
settings = get_settings()

app = FastAPI(
    title="AI Trading Bot",
    description=(
        "Trading automatico basato su Google Gemini Pro per XAUUSD su Interactive Brokers.\n"
        "Fornisce strategie dinamiche, risk management rigido e integrazione con tradeBotNotify."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Configurazione CORS per eventuale dashboard frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoint Base & Health Check
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["Diagnostica"],
)
async def health_check() -> HealthResponse:
    """Verifica che il servizio sia attivo e risponda correttamente."""
    cfg = get_settings()
    uptime = time.time() - _START_TIME
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=cfg.app_env,
        trading_enabled=cfg.trading_enabled,
        uptime_seconds=round(uptime, 2),
    )


@app.get(
    "/status",
    response_model=StatusResponse,
    summary="Stato completo dell'applicazione",
    tags=["Diagnostica"],
)
async def get_status() -> StatusResponse:
    """Restituisce lo stato globale: salute, connessioni, portfolio e bot."""
    cfg = get_settings()
    uptime = time.time() - _START_TIME
    db = get_db()
    db_healthy = await db.is_healthy()

    health = HealthResponse(
        status="ok" if db_healthy else "degraded",
        version=__version__,
        environment=cfg.app_env,
        trading_enabled=cfg.trading_enabled,
        uptime_seconds=round(uptime, 2),
    )

    return StatusResponse(
        health=health,
        portfolio=None,
        ibkr_connected=False,  # Sarà gestito da IBKRConnector in Fase 2
        ai_engine_ready=bool(cfg.gemini_api_key),
        last_analysis=None,
        next_analysis=None,
    )


# ---------------------------------------------------------------------------
# Endpoint Configurazioni
# ---------------------------------------------------------------------------
@app.get(
    "/config/trading-params",
    summary="Parametri di trading attuali",
    tags=["Configurazione"],
)
async def get_trading_params() -> dict[str, Any]:
    """Restituisce i parametri di trading rigidi configurati per gli asset."""
    try:
        return load_trading_params()
    except Exception as e:
        logger.error("Errore lettura trading_params.json", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossibile caricare i parametri di trading",
        )


@app.get(
    "/config/symbols",
    summary="Configurazione simboli",
    tags=["Configurazione"],
)
async def get_symbols() -> dict[str, Any]:
    """Restituisce la configurazione dei simboli abilitati."""
    try:
        return load_symbols_config()
    except Exception as e:
        logger.error("Errore lettura symbols.json", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossibile caricare la configurazione dei simboli",
        )


@app.get(
    "/config/prompts",
    summary="Template prompt AI",
    tags=["Configurazione"],
)
async def get_ai_prompts() -> dict[str, Any]:
    """Restituisce i template dei prompt utilizzati con Google Gemini."""
    try:
        return load_ai_prompts()
    except Exception as e:
        logger.error("Errore lettura ai_prompts.json", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossibile caricare i template dei prompt",
        )


# ---------------------------------------------------------------------------
# Endpoint Trade & Decisioni AI
# ---------------------------------------------------------------------------
@app.get(
    "/trades/daily",
    summary="Trade eseguiti oggi",
    tags=["Trading"],
)
async def get_daily_trades() -> dict[str, Any]:
    """Restituisce i trade completati oggi e le statistiche giornaliere."""
    db = get_db()
    trades = await db.get_daily_trades()
    stats = await db.get_daily_stats()
    return {"stats": stats, "trades": trades}


@app.get(
    "/ai/decisions",
    summary="Ultime decisioni del motore AI",
    tags=["AI Engine"],
)
async def get_ai_decisions(limit: int = 20) -> list[dict[str, Any]]:
    """Restituisce la cronologia delle decisioni prese da Gemini Pro."""
    db = get_db()
    return await db.get_recent_ai_decisions(limit=min(limit, 100))


# ---------------------------------------------------------------------------
# Endpoint Controllo Bot
# ---------------------------------------------------------------------------
@app.post(
    "/bot/start",
    summary="Avvia il bot di trading",
    tags=["Controllo Bot"],
)
async def start_bot() -> dict[str, str]:
    """Abilita il trading automatico."""
    cfg = get_settings()
    cfg.trading_enabled = True
    db = get_db()
    await db.set_config("trading_enabled", True)
    logger.info("Bot avviato manualmente dall'utente")
    return {"status": "started", "trading_enabled": "true"}


@app.post(
    "/bot/stop",
    summary="Arresta il bot di trading",
    tags=["Controllo Bot"],
)
async def stop_bot() -> dict[str, str]:
    """Disabilita il trading automatico (mantiene posizioni esistenti)."""
    cfg = get_settings()
    cfg.trading_enabled = False
    db = get_db()
    await db.set_config("trading_enabled", False)
    logger.info("Bot arrestato manualmente dall'utente")
    return {"status": "stopped", "trading_enabled": "false"}


@app.post(
    "/bot/emergency-stop",
    summary="Arresto di emergenza immediato",
    tags=["Controllo Bot"],
)
async def emergency_stop() -> dict[str, str]:
    """
    Arresto di emergenza:
    - Disabilita immediatamente il trading
    - Registra evento a database
    - Restituisce stato di stop
    """
    cfg = get_settings()
    cfg.trading_enabled = False
    db = get_db()
    await db.set_config("trading_enabled", False)
    await db.set_config("emergency_stopped", True)
    logger.critical("EMERGENCY STOP ATTIVATO DALL'UTENTE")
    return {
        "status": "emergency_stopped",
        "trading_enabled": "false",
        "action": "Tutte le operazioni automatiche bloccate",
    }


# ---------------------------------------------------------------------------
# Gestione Errori Globale
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Any, exc: Exception) -> JSONResponse:
    """Handler globale per catturare eccezioni non gestite."""
    logger.error("Errore interno non gestito", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Errore interno del server", "type": type(exc).__name__},
    )
