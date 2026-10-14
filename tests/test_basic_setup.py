"""
tests/test_basic_setup.py - Test unitari per il setup base della Fase 1.

Verifica:
- Caricamento corretto delle configurazioni (settings, trading_params, symbols, ai_prompts)
- Funzionamento del database SQLite (connessione, tabelle, read/write)
- Funzionamento degli helper
- Funzionamento dei modelli Pydantic
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio

from app.config import (
    BASE_DIR,
    CONFIG_DIR,
    get_settings,
    load_ai_prompts,
    load_symbols_config,
    load_trading_params,
    reload_settings,
)
from app.models import (
    AITradeStrategy,
    HealthResponse,
    MarketSnapshot,
    Position,
    TradeAction,
    TradingDirection,
)
from data.database import Database
from utils.helpers import (
    calculate_pnl,
    calculate_stop_loss,
    calculate_take_profit,
    generate_order_id,
    generate_trade_id,
    round_price,
)


class TestConfigLoading:
    """Test caricamento e validazione configurazioni."""

    def test_settings_default_values(self):
        """Verifica i valori di default delle impostazioni."""
        settings = reload_settings()
        assert settings.app_name == "AI-Trading-Bot"
        assert settings.app_port == 8080
        assert settings.ibkr_host == "192.168.1.212"
        assert settings.ibkr_port == 4004
        assert settings.ibkr_client_id == 500
        assert settings.trading_enabled is False
        assert settings.trading_mode == "paper"

    def test_load_trading_params(self):
        """Verifica il parsing del file trading_params.json."""
        params = load_trading_params()
        assert "assets" in params
        assert "XAUUSD" in params["assets"]
        xau = params["assets"]["XAUUSD"]
        assert xau["risk_management"]["max_budget_per_trade_usd"] == 5000.0
        assert xau["risk_management"]["stop_loss_pct"] == 0.005
        assert xau["risk_management"]["take_profit_pct"] == 0.01
        assert xau["risk_management"]["min_ai_confidence"] == 0.70

    def test_load_symbols_config(self):
        """Verifica il parsing del file symbols.json."""
        symbols = load_symbols_config()
        assert "symbols" in symbols
        assert "XAUUSD" in symbols["symbols"]
        assert symbols["symbols"]["XAUUSD"]["sec_type"] == "CFD"
        assert symbols["symbols"]["XAUUSD"]["contract_size"] == 1.0

    def test_load_ai_prompts(self):
        """Verifica il parsing del file ai_prompts.json."""
        prompts = load_ai_prompts()
        assert "prompts" in prompts
        assert "market_analysis" in prompts["prompts"]
        assert "position_management" in prompts["prompts"]
        assert "emergency_assessment" in prompts["prompts"]


class TestModels:
    """Test validazione modelli Pydantic."""

    def test_market_snapshot_model(self):
        """Verifica la creazione e validazione di MarketSnapshot."""
        snapshot = MarketSnapshot(
            symbol="XAUUSD",
            current_price=2650.50,
            bid=2650.40,
            ask=2650.60,
            spread=0.20,
        )
        assert snapshot.symbol == "XAUUSD"
        assert snapshot.current_price == 2650.50
        assert snapshot.spread == 0.20

    def test_ai_trade_strategy_model(self):
        """Verifica la creazione e validazione di AITradeStrategy."""
        strat = AITradeStrategy(
            action=TradeAction.BUY,
            confidence=0.85,
            reasoning="Trend rialzista confermato da EMA cross e RSI a 55",
            entry_price=2650.0,
            stop_loss=2636.75,
            take_profit=2676.5,
            position_size_oz=1.0,
        )
        assert strat.action == TradeAction.BUY
        assert strat.confidence == 0.85
        assert strat.position_size_oz == 1.0

    def test_health_response_model(self):
        """Verifica il modello HealthResponse."""
        health = HealthResponse(
            status="ok",
            version="0.1.0",
            environment="development",
            trading_enabled=False,
            uptime_seconds=12.5,
        )
        assert health.status == "ok"


class TestHelpers:
    """Test funzioni di utilità."""

    def test_round_price(self):
        """Verifica l'arrotondamento al tick size."""
        assert round_price(2650.126, tick_size=0.01) == 2650.13
        assert round_price(2650.124, tick_size=0.01) == 2650.12
        assert round_price(2650.125, tick_size=0.01) == 2650.13

    def test_calculate_pnl_long(self):
        """Verifica il calcolo P&L per posizioni long."""
        # Compra a 2600, vende a 2650, quantità 2 -> guadagno 100
        pnl = calculate_pnl(entry_price=2600.0, current_price=2650.0, quantity=2.0, direction="long")
        assert pnl == 100.0

    def test_calculate_pnl_short(self):
        """Verifica il calcolo P&L per posizioni short."""
        # Vende a 2650, ricompra a 2600, quantità 1 -> guadagno 50
        pnl = calculate_pnl(entry_price=2650.0, current_price=2600.0, quantity=1.0, direction="short")
        assert pnl == 50.0

    def test_calculate_stop_loss(self):
        """Verifica il calcolo dello stop loss per long e short."""
        sl_long = calculate_stop_loss(2000.0, 0.005, direction="long")
        assert sl_long == 1990.0

        sl_short = calculate_stop_loss(2000.0, 0.005, direction="short")
        assert sl_short == 2010.0

    def test_calculate_take_profit(self):
        """Verifica il calcolo del take profit."""
        tp_long = calculate_take_profit(2000.0, 0.01, direction="long")
        assert tp_long == 2020.0

        tp_short = calculate_take_profit(2000.0, 0.01, direction="short")
        assert tp_short == 1980.0

    def test_id_generation(self):
        """Verifica la generazione di ID univoci."""
        tid = generate_trade_id()
        oid = generate_order_id()
        assert tid.startswith("TRD-")
        assert oid.startswith("ORD-")
        assert len(tid) > 8
        assert len(oid) > 8


@pytest.mark.asyncio
class TestDatabase:
    """Test asincroni per il layer database SQLite."""

    async def test_database_lifecycle_and_config(self, tmp_path):
        """Verifica ciclo di vita del database e operazioni config."""
        test_db_path = tmp_path / "test_trading.db"
        db = Database(db_path=test_db_path)

        # Connessione
        await db.connect()
        assert await db.is_healthy() is True

        # Read/Write config
        await db.set_config("test_key", {"foo": "bar", "val": 42})
        val = await db.get_config("test_key")
        assert val == {"foo": "bar", "val": 42}

        # Chiave inesistente
        default_val = await db.get_config("nonexistent", default="default")
        assert default_val == "default"

        # AI Decisions
        row_id = await db.record_ai_decision(
            symbol="XAUUSD",
            action="BUY",
            confidence=0.88,
            reasoning="Test signal",
            executed=True,
        )
        assert row_id > 0

        decisions = await db.get_recent_ai_decisions(limit=5)
        assert len(decisions) >= 1
        assert decisions[0]["symbol"] == "XAUUSD"
        assert decisions[0]["action"] == "BUY"

        # Disconnessione
        await db.disconnect()
