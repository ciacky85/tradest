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
from integration.ibkr_client import IBKRClient, get_ibkr_client
from utils.logger import get_logger, setup_logging

# Timestamp di avvio applicazione per il calcolo dell'uptime
_START_TIME = time.time()

logger = get_logger("app.main")


# ---------------------------------------------------------------------------
# Modelli Pydantic per le API di Gemini
# ---------------------------------------------------------------------------
class GeminiConfigRequest(BaseModel):
    provider: Optional[str] = "omniroute"  # 'omniroute' oppure 'google'
    base_url: Optional[str] = "http://192.168.1.212:9292/v1"
    api_key: Optional[str] = "sk-92fbd7ff0bd42a7d-82e301-62dbdb1f"
    model: Optional[str] = "carlo-gemini"
    temperature: Optional[float] = 0.2


class IBKRConfigRequest(BaseModel):
    host: Optional[str] = "192.168.1.212"
    port: Optional[int] = 4004
    client_id: Optional[int] = 500
    account_id: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    trading_mode: Optional[str] = "paper"  # 'paper' o 'live'


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

        # Ripristina configurazione AI salvata se presente
        saved_prov = await db.get_config("ai_provider")
        saved_url = await db.get_config("ai_base_url")
        saved_key = await db.get_config("ai_api_key") or await db.get_config("gemini_api_key")
        saved_model = await db.get_config("gemini_model")
        saved_temp = await db.get_config("gemini_temperature")

        client = get_gemini_client()
        if saved_prov:
            client.provider = saved_prov
            settings.ai_provider = saved_prov
        if saved_url:
            client.base_url = saved_url
            settings.ai_base_url = saved_url
        if saved_key:
            client.set_api_key(saved_key)
        if saved_model:
            client.set_model(saved_model)
            settings.gemini_model = saved_model
        if saved_temp is not None:
            settings.gemini_temperature = float(saved_temp)

        # Ripristina configurazione IBKR salvata se presente
        ib_client = get_ibkr_client()
        saved_ib_user = await db.get_config("ibkr_username")
        saved_ib_pw = await db.get_config("ibkr_password")
        saved_ib_mode = await db.get_config("trading_mode")
        saved_ib_host = await db.get_config("ibkr_host")
        saved_ib_port = await db.get_config("ibkr_port")
        saved_ib_acc = await db.get_config("ibkr_account_id")

        ib_client.update_credentials(
            username=saved_ib_user or settings.ibkr_username,
            password=saved_ib_pw or settings.ibkr_password,
            trading_mode=saved_ib_mode or settings.trading_mode,
            host=saved_ib_host or settings.ibkr_host,
            port=int(saved_ib_port) if saved_ib_port else settings.ibkr_port,
            account_id=saved_ib_acc or settings.ibkr_account_id,
        )

    except Exception as exc:
        logger.error("Errore inizializzazione database", error=str(exc))

    # Startup: ripristina bot precedentemente attivi su ciascun simbolo
    try:
        from strategy.bot_engine import get_bot_engine
        engine = get_bot_engine()
        await engine.initialize_from_db()
    except Exception as exc:
        logger.warning("Ripristino bot in background fallito", exc=str(exc))

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
    summary="Recupera la configurazione attuale di AI (Omniroute / Google)",
    tags=["Google Gemini"],
)
async def get_gemini_config() -> dict[str, Any]:
    """Restituisce provider, base_url, modello e API Key mascherata."""
    cfg = get_settings()
    client = get_gemini_client()
    key = client.api_key
    masked = (key[:6] + "..." + key[-4:]) if len(key) > 10 else ("***" if key else "")
    # Se il provider è omniroute e la chiave corrisponde a quella di default o è impostata,
    # restituiamo la chiave non mascherata o un flag per evitare che l'utente salvi per sbaglio una stringa mascherata
    return {
        "provider": client.provider,
        "base_url": client.base_url,
        "has_api_key": bool(key),
        "api_key": key if client.provider == "omniroute" else "",
        "api_key_masked": masked,
        "model": client.model or cfg.gemini_model,
        "temperature": cfg.gemini_temperature,
    }


@app.post(
    "/api/gemini/config",
    summary="Salva configurazione AI (Omniroute / Google)",
    tags=["Google Gemini"],
)
async def save_gemini_config(req: GeminiConfigRequest) -> dict[str, Any]:
    """Aggiorna provider (omniroute/google), endpoint, modello e chiave."""
    cfg = get_settings()
    client = get_gemini_client()
    db = get_db()

    if req.provider is not None:
        client.provider = req.provider.strip().lower()
        cfg.ai_provider = client.provider
        await db.set_config("ai_provider", client.provider)

    if req.base_url is not None:
        client.base_url = req.base_url.strip().rstrip("/")
        cfg.ai_base_url = client.base_url
        await db.set_config("ai_base_url", client.base_url)

    if req.api_key and req.api_key.strip():
        clean_key = req.api_key.strip()
        # Ignora se l'utente invia accidentalmente la stringa mascherata
        if "..." not in clean_key and clean_key != "***":
            client.set_api_key(clean_key)
            if client.provider == "omniroute":
                cfg.ai_api_key = clean_key
                await db.set_config("ai_api_key", clean_key)
            else:
                cfg.gemini_api_key = clean_key
                await db.set_config("gemini_api_key", clean_key)

    if req.model and req.model.strip():
        clean_model = req.model.strip()
        client.set_model(clean_model)
        cfg.gemini_model = clean_model
        await db.set_config("gemini_model", clean_model)

    if req.temperature is not None:
        cfg.gemini_temperature = req.temperature
        await db.set_config("gemini_temperature", str(req.temperature))

    logger.info("Configurazione AI aggiornata", provider=client.provider, model=client.model)
    return {
        "status": "updated",
        "provider": client.provider,
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


class AnalysisRequest(BaseModel):
    symbol: Optional[str] = "XAUUSD"
    budget: Optional[float] = None


@app.post(
    "/api/gemini/simulate-trade",
    summary="Analizza il titolo selezionato (30gg/7gg) e definisce la strategia di scalping",
    tags=["Google Gemini"],
)
async def simulate_trade(req: Optional[AnalysisRequest] = None) -> dict[str, Any]:
    """
    Analizza l'andamento del titolo selezionato (XAUUSD, NVDA, SPCX, IB1T, ecc.) negli ultimi 30 giorni
    e nell'ultima settimana, calcola gli indicatori tecnici, verifica il portafoglio reale e la saturazione
    del budget (quote intere, divieto di acquisto se già a budget) e genera la strategia con l'AI.
    """
    client = get_gemini_client()
    if not client.api_key:
        return {
            "error": "Chiave API AI non configurata. Inseriscila nelle impostazioni della dashboard."
        }

    sym = (req.symbol if req and req.symbol else "XAUUSD").upper().strip()
    custom_budget = req.budget if req and req.budget and req.budget > 0 else None

    try:
        from strategy.scalping_strategy import get_scalping_manager

        manager = get_scalping_manager()
        strategy = await manager.analyze_and_generate_strategy(symbol=sym, custom_budget=custom_budget)
        return strategy
    except Exception as e:
        logger.error(f"Errore analisi e generazione strategia per {sym}", exc=str(e))
        return {"error": f"Errore durante l'analisi: {str(e)}"}


@app.get(
    "/api/symbols/budget",
    summary="Recupera i budget salvati per i titoli",
    tags=["Parametri Trading"],
)
async def get_symbols_budget() -> dict[str, Any]:
    """Restituisce la mappa dei budget impostati per ciascun titolo."""
    db = get_db()
    custom_budgets = await db.get_config("symbols_budget", {})
    return {"symbols_budget": custom_budgets}


@app.post(
    "/api/symbols/budget",
    summary="Salva il budget per un titolo",
    tags=["Parametri Trading"],
)
async def save_symbol_budget(req: dict[str, Any]) -> dict[str, Any]:
    """Aggiorna e rende persistente il budget allocato per un titolo."""
    sym = str(req.get("symbol", "XAUUSD")).upper().strip()
    budget = float(req.get("budget", 5000.0))
    from strategy.scalping_strategy import get_scalping_manager

    manager = get_scalping_manager()
    await manager.set_symbol_budget(sym, budget)
    return {"status": "saved", "symbol": sym, "budget": budget}


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

    ib_client = get_ibkr_client()
    portfolio = await ib_client.get_portfolio()

    return StatusResponse(
        health=health,
        portfolio=portfolio,
        ibkr_connected=ib_client.is_connected,
        ai_engine_ready=bool(client.api_key or cfg.gemini_api_key),
        last_analysis=None,
        next_analysis=None,
    )


# ---------------------------------------------------------------------------
# Endpoint Interactive Brokers (IBKR)
# ---------------------------------------------------------------------------
@app.get(
    "/portfolio",
    summary="Dati correnti del portafoglio",
    tags=["Trading"],
)
async def get_portfolio() -> dict[str, Any]:
    """
    Restituisce le informazioni complete e aggiornate sul portafoglio da Interactive Brokers:
    liquidità, cash, buying power, posizioni aperte con P&L, ordini ed esecuzioni.
    """
    ib_client = get_ibkr_client()
    return await ib_client.get_all_account_data()


@app.get(
    "/api/ibkr/config",
    summary="Stato configurazione Interactive Brokers",
    tags=["Interactive Brokers"],
)
async def get_ibkr_config() -> dict[str, Any]:
    """Restituisce la configurazione attuale di IBKR Gateway e dell'utenza."""
    ib_client = get_ibkr_client()
    cfg = get_settings()
    masked_pw = ("*" * len(ib_client.password)) if ib_client.password else ""
    return {
        "host": ib_client.host,
        "port": ib_client.port,
        "client_id": ib_client.client_id,
        "account_id": ib_client.account_id,
        "username": ib_client.username,
        "has_password": bool(ib_client.password),
        "masked_password": masked_pw,
        "trading_mode": ib_client.trading_mode,
        "connected": ib_client.is_connected,
    }


@app.post(
    "/api/ibkr/config",
    summary="Salva configurazione e credenziali Interactive Brokers",
    tags=["Interactive Brokers"],
)
async def update_ibkr_config(req: IBKRConfigRequest) -> dict[str, Any]:
    """Salva credenziali IBKR (username, password, paper/live mode, host, port) nel database persistente."""
    ib_client = get_ibkr_client()
    cfg = get_settings()
    db = get_db()

    if req.username is not None:
        ib_client.username = req.username.strip()
        cfg.ibkr_username = ib_client.username
        await db.set_config("ibkr_username", ib_client.username)

    if req.password is not None and req.password != "":
        ib_client.password = req.password.strip()
        cfg.ibkr_password = ib_client.password
        await db.set_config("ibkr_password", ib_client.password)

    if req.trading_mode is not None:
        ib_client.trading_mode = req.trading_mode.strip()
        cfg.trading_mode = ib_client.trading_mode
        await db.set_config("trading_mode", ib_client.trading_mode)

    if req.host is not None:
        ib_client.host = req.host.strip()
        cfg.ibkr_host = ib_client.host
        await db.set_config("ibkr_host", ib_client.host)

    if req.port is not None:
        ib_client.port = req.port
        cfg.ibkr_port = ib_client.port
        await db.set_config("ibkr_port", str(ib_client.port))

    if req.account_id is not None:
        ib_client.account_id = req.account_id.strip()
        cfg.ibkr_account_id = ib_client.account_id
        await db.set_config("ibkr_account_id", ib_client.account_id)

    logger.info(
        "Configurazione IBKR salvata con successo",
        username=ib_client.username,
        trading_mode=ib_client.trading_mode,
        host=ib_client.host,
        port=ib_client.port,
    )
    return {
        "status": "success",
        "message": "Configurazione IBKR aggiornata con successo",
        "trading_mode": ib_client.trading_mode,
        "username": ib_client.username,
    }


@app.post(
    "/api/ibkr/test",
    summary="Test connessione a Interactive Brokers",
    tags=["Interactive Brokers"],
)
async def test_ibkr_connection() -> dict[str, Any]:
    """Testa la connessione al Gateway / TWS di Interactive Brokers."""
    ib_client = get_ibkr_client()
    is_ok = await ib_client.connect(timeout=5.0)
    if is_ok:
        portfolio = await ib_client.get_portfolio()
        return {
            "success": True,
            "connected": True,
            "message": f"Connessione a IBKR stabilita con successo ({ib_client.host}:{ib_client.port})",
            "trading_mode": ib_client.trading_mode,
            "account_id": portfolio.account.account_id,
            "net_liquidation": portfolio.account.total_value,
            "total_cash": portfolio.account.cash_balance,
            "positions_count": len(portfolio.positions),
        }
    else:
        return {
            "success": False,
            "connected": False,
            "message": f"Impossibile connettersi a IBKR Gateway ({ib_client.host}:{ib_client.port}). Verificare che il container Gateway/TWS sia avviato e in ascolto.",
            "trading_mode": ib_client.trading_mode,
            "host": ib_client.host,
            "port": ib_client.port,
        }


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
class BotControlRequest(BaseModel):
    symbol: Optional[str] = "XAUUSD"


@app.post(
    "/bot/start",
    summary="Avvia il bot di trading per il titolo selezionato",
    tags=["Controllo Bot"],
)
async def start_bot(req: Optional[BotControlRequest] = None) -> dict[str, Any]:
    """
    Abilita il trading automatico in background per il singolo titolo,
    verificando la disponibilità di budget e strategia valida.
    """
    sym = (req.symbol if req and req.symbol else "XAUUSD").upper().strip()
    from strategy.scalping_strategy import get_scalping_manager
    from strategy.bot_engine import get_bot_engine

    manager = get_scalping_manager()
    readiness = await manager.validate_auto_trading_readiness(symbol=sym)

    if not readiness["can_start"]:
        raise HTTPException(
            status_code=400,
            detail=readiness.get("reason", f"Impossibile avviare il trading su {sym}"),
        )

    engine = get_bot_engine()
    engine.start_symbol_bot(sym)

    cfg = get_settings()
    cfg.trading_enabled = True
    db = get_db()
    await db.set_config("trading_enabled", True)

    return {
        "status": "started",
        "symbol": sym,
        "is_active": True,
        "active_strategy": readiness.get("strategy"),
        "account": readiness.get("account"),
    }


@app.post(
    "/bot/stop",
    summary="Arresta il bot di trading per il titolo",
    tags=["Controllo Bot"],
)
async def stop_bot(req: Optional[BotControlRequest] = None) -> dict[str, Any]:
    """Arresta il task in background per il titolo indicato."""
    sym = (req.symbol if req and req.symbol else "XAUUSD").upper().strip()
    from strategy.bot_engine import get_bot_engine

    engine = get_bot_engine()
    await engine.stop_symbol_bot(sym)

    return {"status": "stopped", "symbol": sym, "is_active": False}


@app.get(
    "/bot/status/all",
    summary="Restituisce lo stato di tutti i bot per ciascun titolo",
    tags=["Controllo Bot"],
)
async def get_all_bots_status() -> dict[str, Any]:
    """Verifica quali bot sono attivi in background per ciascun simbolo."""
    from strategy.bot_engine import get_bot_engine

    engine = get_bot_engine()
    return {"bots": engine.get_all_bots_status()}


@app.get(
    "/bot/logs",
    summary="Recupera i log dettagliati di trading (persistenti)",
    tags=["Controllo Bot"],
)
async def get_bot_logs(symbol: Optional[str] = None, limit: int = 100) -> dict[str, Any]:
    """
    Restituisce la cronologia dei log di esecuzione dal database SQLite,
    filtrabili per simbolo (es. XAUUSD, NVDA).
    """
    db = get_db()
    logs = await db.get_bot_logs(symbol=symbol, limit=limit)
    return {"symbol": symbol, "logs": logs, "count": len(logs)}


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
