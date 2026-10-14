"""
app/main.py - Entry point dell'applicazione FastAPI AI Trading Bot.

Fornisce:
- Dashboard Web UI su `/` per gestione, autenticazione Google Gemini e monitoraggio
- Lifespan handler per startup e shutdown asincrono
- Endpoint di health check e diagnostica
- Endpoint per configurazione Google Gemini (API key, modello dinamico, test connessione)
- Endpoint per consultare portfolio, ordini e trade
- Endpoint per controllo manuale del bot (start/stop/pause)
- Endpoint per consultare e simulare le decisioni AI
- Documentazione Swagger/OpenAPI interattiva su `/docs`
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app import __version__
from app.config import (
    BASE_DIR,
    get_settings,
    load_ai_prompts,
    load_symbols_config,
    load_trading_params,
)
from app.models import HealthResponse, StatusResponse
from data.database import Database, get_db
from integration.gemini_client import GeminiClient, get_gemini_client
from utils.logger import get_logger, setup_logging

# Timestamp di avvio applicazione per il calcolo dell'uptime
_START_TIME = time.time()

logger = get_logger("app.main")


# ---------------------------------------------------------------------------
# Modelli Pydantic per le API di Gemini
# ---------------------------------------------------------------------------
class GeminiConfigRequest(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = "gemini-1.5-pro"
    temperature: Optional[float] = 0.2


# ---------------------------------------------------------------------------
# Lifespan context manager (startup e shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestisce il ciclo di vita dell'applicazione: startup e shutdown."""
    # --- STARTUP ---
    setup_logging()
    settings = get_settings()
    logger.info(
        "Avvio AI Trading Bot Tradest",
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

        # Ripristina configurazione Gemini salvata se presente
        saved_key = await db.get_config("gemini_api_key")
        saved_model = await db.get_config("gemini_model")
        saved_temp = await db.get_config("gemini_temperature")

        client = get_gemini_client()
        if saved_key:
            client.set_api_key(saved_key)
            settings.gemini_api_key = saved_key
        if saved_model:
            client.set_model(saved_model)
            settings.gemini_model = saved_model
        if saved_temp is not None:
            settings.gemini_temperature = float(saved_temp)

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
    title="Tradest - AI Trading Bot",
    description=(
        "Trading automatico basato su Google Gemini per XAUUSD su Interactive Brokers.\n"
        "Fornisce strategie dinamiche, selezione modello AI, risk management rigido e integrazione tradeBotNotify."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Configurazione CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dashboard Web UI
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, summary="Dashboard Web UI", tags=["Dashboard"])
async def get_dashboard() -> HTMLResponse:
    """Restituisce la dashboard Web HTML di controllo e autenticazione Google Gemini."""
    template_path = BASE_DIR / "app" / "templates" / "index.html"
    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
        return HTMLResponse(content=content)
    return HTMLResponse(
        content="<h1>Tradest AI Trading Bot</h1><p>Dashboard template in caricamento...</p>"
    )


# ---------------------------------------------------------------------------
# Endpoint Google Gemini AI (Autenticazione, Selezione Modello, Test)
# ---------------------------------------------------------------------------
@app.get(
    "/api/gemini/config",
    summary="Recupera la configurazione attuale di Gemini",
    tags=["Google Gemini"],
)
async def get_gemini_config() -> dict[str, Any]:
    """Restituisce lo stato dell'API Key (mascherata) e il modello attualmente selezionato."""
    cfg = get_settings()
    client = get_gemini_client()
    key = client.api_key or cfg.gemini_api_key
    masked = (key[:6] + "..." + key[-4:]) if len(key) > 10 else ("***" if key else "")
    return {
        "has_api_key": bool(key),
        "api_key_masked": masked,
        "model": client.model or cfg.gemini_model,
        "temperature": cfg.gemini_temperature,
    }


@app.post(
    "/api/gemini/config",
    summary="Salva API Key e modello selezionato per Gemini",
    tags=["Google Gemini"],
)
async def save_gemini_config(req: GeminiConfigRequest) -> dict[str, Any]:
    """Aggiorna l'API key Google e il modello selezionato nel database e a runtime."""
    cfg = get_settings()
    client = get_gemini_client()
    db = get_db()

    if req.api_key and req.api_key.strip():
        clean_key = req.api_key.strip()
        client.set_api_key(clean_key)
        cfg.gemini_api_key = clean_key
        await db.set_config("gemini_api_key", clean_key)

    if req.model and req.model.strip():
        clean_model = req.model.strip()
        client.set_model(clean_model)
        cfg.gemini_model = clean_model
        await db.set_config("gemini_model", clean_model)

    if req.temperature is not None:
        cfg.gemini_temperature = req.temperature
        await db.set_config("gemini_temperature", req.temperature)

    logger.info("Configurazione Gemini aggiornata", model=client.model)
    return {
        "status": "updated",
        "model": client.model,
        "has_api_key": bool(client.api_key),
    }


@app.get(
    "/api/gemini/models",
    summary="Elenco modelli Google Gemini disponibili",
    tags=["Google Gemini"],
)
async def get_gemini_models() -> dict[str, Any]:
    """Interroga l'API di Google per restituire i modelli supportati per l'account."""
    client = get_gemini_client()
    models = await client.list_available_models()
    return {"models": models, "active_model": client.model}


@app.post(
    "/api/gemini/test",
    summary="Test rapido connessione Google Gemini",
    tags=["Google Gemini"],
)
async def test_gemini() -> dict[str, Any]:
    """Invia un prompt di test al modello selezionato per validare l'autenticazione."""
    client = get_gemini_client()
    result = await client.test_connection()
    return result


@app.post(
    "/api/gemini/simulate-trade",
    summary="Simula analisi strategica con Gemini su XAUUSD",
    tags=["Google Gemini"],
)
async def simulate_trade() -> dict[str, Any]:
    """
    Esegue una richiesta completa di analisi a Gemini con dati di mercato simulati
    per verificare che il modello comunichi correttamente le scelte di trade.
    """
    client = get_gemini_client()
    if not client.api_key:
        return {
            "error": "Google Gemini API Key non configurata. Inseriscila nelle impostazioni della dashboard."
        }

    prompts = load_ai_prompts()
    ma_prompt = prompts["prompts"]["market_analysis"]
    sys_instruction = ma_prompt["system_instruction"]
    template = ma_prompt["analysis_template"]

    # Dati simulati di contesto XAUUSD
    filled_prompt = template.format(
        symbol="XAUUSD",
        current_price=2654.80,
        bid=2654.60,
        ask=2655.00,
        spread=0.40,
        volume=14200.0,
        daily_change_pct=+0.65,
        rsi=58.4,
        ema_fast=2652.10,
        ema_slow=2648.50,
        macd=1.85,
        macd_signal=1.20,
        macd_hist=0.65,
        atr=3.40,
        bb_upper=2660.00,
        bb_middle=2651.00,
        bb_lower=2642.00,
        open_positions="Nessuna posizione aperta al momento.",
        recent_trades="Ultimi 3 trade: +$18.50, +$14.20, -$8.00 (Win rate 66%)",
        daily_pnl=+24.70,
        trades_today=3,
        win_rate_today=66.7,
        max_budget=5000.0,
        stop_loss_pct=0.005,
        take_profit_pct=0.01,
        allowed_direction="both",
        max_position_size=2.0,
    )

    try:
        response = await client.generate_trade_analysis(
            prompt=filled_prompt,
            system_instruction=sys_instruction,
        )

        # Registra la simulazione nel DB SQLite per storico decisioni
        db = get_db()
        await db.record_ai_decision(
            symbol="XAUUSD",
            action=response.get("action", "HOLD"),
            confidence=float(response.get("confidence", 0.0)),
            reasoning=response.get("reasoning", ""),
            market_sentiment=response.get("market_sentiment", "NEUTRAL"),
            entry_price=response.get("entry_price"),
            stop_loss=response.get("stop_loss"),
            take_profit=response.get("take_profit"),
            position_size_oz=response.get("position_size_oz", 0.0),
            urgency=response.get("urgency", "LOW"),
            risk_reward_ratio=response.get("risk_reward_ratio", 0.0),
            executed=False,
            rejection_reason="Simulazione manuale da Web Dashboard",
        )

        return response
    except Exception as e:
        logger.error("Errore simulazione trade con Gemini", error=str(e))
        return {"error": str(e)}


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
    client = get_gemini_client()
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
        ibkr_connected=False,
        ai_engine_ready=bool(client.api_key or cfg.gemini_api_key),
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
    """Restituisce la cronologia delle decisioni prese da Gemini."""
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
