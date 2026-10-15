"""
data/database.py - Gestione persistenza SQLite asincrona con aiosqlite.

Fornisce la classe Database con schema per:
- Configurazione e parametri runtime
- Storico trade eseguiti
- Log decisioni AI
- Snapshot portfolio periodici
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from app.config import DATA_STORAGE_DIR, get_settings
from app.models import Position, TradeRecord
from utils.logger import get_logger

logger = get_logger("database")

# Schema SQL per inizializzazione database
INIT_SQL = """
-- Tabella configurazioni runtime (chiave-valore)
CREATE TABLE IF NOT EXISTS runtime_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella storico trade eseguiti
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    direction TEXT NOT NULL,
    quantity REAL NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    pnl REAL NOT NULL,
    commission REAL DEFAULT 0.0,
    ai_confidence REAL NOT NULL,
    ai_reasoning TEXT,
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP NOT NULL,
    hold_time_minutes REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella log decisioni AI (sia trade eseguiti che scartati)
CREATE TABLE IF NOT EXISTS ai_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    confidence REAL NOT NULL,
    reasoning TEXT,
    market_sentiment TEXT,
    entry_price REAL,
    stop_loss REAL,
    take_profit REAL,
    position_size_oz REAL,
    urgency TEXT,
    risk_reward_ratio REAL,
    executed INTEGER DEFAULT 0,
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella snapshot portfolio periodici
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_value REAL NOT NULL,
    cash_balance REAL NOT NULL,
    buying_power REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    realized_pnl_today REAL NOT NULL,
    open_positions_count INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella ordini
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    order_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL,
    stop_loss REAL,
    take_profit REAL,
    status TEXT NOT NULL,
    fill_price REAL,
    commission REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP
);

-- Indici per performance query frequenti
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON trades(closed_at);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_created ON ai_decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
"""


class Database:
    """Wrapper asincrono per database SQLite con pool di connessione semplice."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            DATA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            self.db_path = str(DATA_STORAGE_DIR / "trading.db")
        else:
            self.db_path = str(db_path)
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Apre la connessione al database e inizializza lo schema."""
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._init_schema()
        logger.info("Database SQLite connesso", path=self.db_path)

    async def disconnect(self) -> None:
        """Chiude la connessione al database."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database SQLite disconnesso")

    async def _init_schema(self) -> None:
        """Crea le tabelle se non esistono."""
        if self._conn:
            await self._conn.executescript(INIT_SQL)
            await self._conn.commit()

    # --- Runtime Config ---

    async def _ensure_connected(self) -> None:
        """Verifica che la connessione sia attiva, altrimenti la inizializza automaticamente."""
        if self._conn is None:
            await self.connect()

    async def set_config(self, key: str, value: Any) -> None:
        """Salva un valore di configurazione (serializzato in JSON)."""
        await self._ensure_connected()
        val_str = json.dumps(value)
        query = """
            INSERT INTO runtime_config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """
        assert self._conn is not None
        await self._conn.execute(query, (key, val_str))
        await self._conn.commit()

    async def get_config(self, key: str, default: Any = None) -> Any:
        """Recupera un valore di configurazione."""
        await self._ensure_connected()
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT value FROM runtime_config WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
            return default

    # --- Trades ---

    async def record_trade(self, trade: TradeRecord) -> None:
        """Registra un trade completato."""
        query = """
            INSERT INTO trades (
                trade_id, symbol, action, direction, quantity,
                entry_price, exit_price, pnl, commission,
                ai_confidence, ai_reasoning, opened_at, closed_at, hold_time_minutes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        assert self._conn is not None
        await self._conn.execute(
            query,
            (
                trade.trade_id,
                trade.symbol,
                trade.action.value,
                trade.direction.value,
                trade.quantity,
                trade.entry_price,
                trade.exit_price,
                trade.pnl,
                trade.commission,
                trade.ai_confidence,
                trade.ai_reasoning,
                trade.opened_at.isoformat(),
                trade.closed_at.isoformat(),
                trade.hold_time_minutes,
            ),
        )
        await self._conn.commit()
        logger.info("Trade registrato a DB", trade_id=trade.trade_id, pnl=trade.pnl)

    async def get_daily_trades(self, date_str: Optional[str] = None) -> list[dict]:
        """Restituisce tutti i trade completati per una certa data (default: oggi)."""
        assert self._conn is not None
        if date_str:
            query = "SELECT * FROM trades WHERE DATE(closed_at) = ? ORDER BY closed_at DESC"
            params = (date_str,)
        else:
            query = "SELECT * FROM trades WHERE DATE(closed_at) = DATE('now') ORDER BY closed_at DESC"
            params = ()
        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_daily_stats(self) -> dict:
        """Calcola statistiche sui trade di oggi."""
        assert self._conn is not None
        query = """
            SELECT
                COUNT(*) as total_trades,
                COALESCE(SUM(pnl), 0.0) as total_pnl,
                COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) as winning_trades,
                COALESCE(SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END), 0) as losing_trades,
                COALESCE(MAX(pnl), 0.0) as best_trade,
                COALESCE(MIN(pnl), 0.0) as worst_trade
            FROM trades
            WHERE DATE(closed_at) = DATE('now')
        """
        async with self._conn.execute(query) as cursor:
            row = await cursor.fetchone()
            if not row:
                return {"total_trades": 0, "total_pnl": 0.0, "win_rate": 0.0}
            total = row["total_trades"]
            wins = row["winning_trades"]
            win_rate = (wins / total * 100) if total > 0 else 0.0
            return {
                "total_trades": total,
                "total_pnl": row["total_pnl"],
                "winning_trades": wins,
                "losing_trades": row["losing_trades"],
                "win_rate": round(win_rate, 2),
                "best_trade": row["best_trade"],
                "worst_trade": row["worst_trade"],
            }

    # --- AI Decisions ---

    async def record_ai_decision(
        self,
        symbol: str,
        action: str,
        confidence: float,
        reasoning: str,
        market_sentiment: str = "NEUTRAL",
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_size_oz: float = 0.0,
        urgency: str = "LOW",
        risk_reward_ratio: float = 0.0,
        executed: bool = False,
        rejection_reason: Optional[str] = None,
    ) -> int:
        """Registra una decisione presa dal motore AI."""
        await self._ensure_connected()
        query = """
            INSERT INTO ai_decisions (
                symbol, action, confidence, reasoning, market_sentiment,
                entry_price, stop_loss, take_profit, position_size_oz,
                urgency, risk_reward_ratio, executed, rejection_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        assert self._conn is not None
        cursor = await self._conn.execute(
            query,
            (
                symbol,
                action,
                confidence,
                reasoning,
                market_sentiment,
                entry_price,
                stop_loss,
                take_profit,
                position_size_oz,
                urgency,
                risk_reward_ratio,
                1 if executed else 0,
                rejection_reason,
            ),
        )
        await self._conn.commit()
        return cursor.lastrowid or 0

    async def get_recent_ai_decisions(self, limit: int = 20) -> list[dict]:
        """Restituisce le ultime decisioni AI."""
        assert self._conn is not None
        query = "SELECT * FROM ai_decisions ORDER BY created_at DESC LIMIT ?"
        async with self._conn.execute(query, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # --- Portfolio Snapshots ---

    async def save_portfolio_snapshot(
        self,
        total_value: float,
        cash_balance: float,
        buying_power: float,
        unrealized_pnl: float,
        realized_pnl_today: float,
        open_positions_count: int,
    ) -> None:
        """Salva uno snapshot dello stato del portfolio."""
        query = """
            INSERT INTO portfolio_snapshots (
                total_value, cash_balance, buying_power,
                unrealized_pnl, realized_pnl_today, open_positions_count
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        assert self._conn is not None
        await self._conn.execute(
            query,
            (
                total_value,
                cash_balance,
                buying_power,
                unrealized_pnl,
                realized_pnl_today,
                open_positions_count,
            ),
        )
        await self._conn.commit()

    # --- Health Check ---

    async def is_healthy(self) -> bool:
        """Verifica che la connessione al database sia attiva e funzionante."""
        try:
            if not self._conn:
                return False
            async with self._conn.execute("SELECT 1") as cursor:
                result = await cursor.fetchone()
                return result is not None and result[0] == 1
        except Exception as e:
            logger.error("Database health check fallito", error=str(e))
            return False


# Singleton globale del database
_db: Optional[Database] = None


def get_db() -> Database:
    """Restituisce l'istanza singleton del database."""
    global _db
    if _db is None:
        _db = Database()
    return _db
