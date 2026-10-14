"""
app/models.py - Modelli dati Pydantic per l'applicazione.

Definisce tutti i modelli usati nell'applicazione: dati di mercato,
ordini, posizioni, risposte AI, notifiche, e stato del portfolio.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ===== Enumerazioni =====

class TradeAction(str, Enum):
    """Azione di trading possibile."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"


class OrderType(str, Enum):
    """Tipo di ordine."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    """Stato di un ordine."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class TradingDirection(str, Enum):
    """Direzione di trading consentita."""
    LONG = "long"
    SHORT = "short"
    BOTH = "both"


class MarketSentiment(str, Enum):
    """Sentiment del mercato valutato dall'AI."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class Urgency(str, Enum):
    """Urgenza dell'operazione suggerita dall'AI."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PositionManagementAction(str, Enum):
    """Azione di gestione posizione."""
    HOLD = "HOLD"
    CLOSE = "CLOSE"
    MODIFY_SL = "MODIFY_SL"
    MODIFY_TP = "MODIFY_TP"
    TRAIL_STOP = "TRAIL_STOP"


class EmergencyAction(str, Enum):
    """Azione raccomandata in caso di emergenza."""
    CONTINUE = "CONTINUE"
    REDUCE_SIZE = "REDUCE_SIZE"
    PAUSE_30MIN = "PAUSE_30MIN"
    STOP_DAY = "STOP_DAY"


# ===== Modelli Dati di Mercato =====

class MarketSnapshot(BaseModel):
    """Snapshot dei dati di mercato in tempo reale."""
    symbol: str
    current_price: float
    bid: float
    ask: float
    spread: float
    volume: float = 0.0
    daily_change_pct: float = 0.0
    daily_high: float = 0.0
    daily_low: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TechnicalIndicators(BaseModel):
    """Indicatori tecnici calcolati."""
    rsi: float = 50.0
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    atr: float = 0.0
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    volume_sma: float = 0.0


class MarketContext(BaseModel):
    """Contesto di mercato completo per l'analisi AI."""
    snapshot: MarketSnapshot
    indicators: TechnicalIndicators
    open_positions: list[Position] = Field(default_factory=list)
    recent_trades: list[TradeRecord] = Field(default_factory=list)
    daily_pnl: float = 0.0
    trades_today: int = 0
    win_rate_today: float = 0.0


# ===== Modelli Posizioni e Ordini =====

class Position(BaseModel):
    """Posizione aperta nel portfolio."""
    symbol: str
    direction: TradingDirection
    quantity: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    hold_time_minutes: float = 0.0


class Order(BaseModel):
    """Ordine di trading."""
    order_id: str = ""
    symbol: str
    action: TradeAction
    order_type: OrderType = OrderType.MARKET
    quantity: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    fill_price: Optional[float] = None
    commission: float = 0.0


class TradeRecord(BaseModel):
    """Record storico di un trade completato."""
    trade_id: str = ""
    symbol: str
    action: TradeAction
    direction: TradingDirection
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    commission: float = 0.0
    ai_confidence: float = 0.0
    ai_reasoning: str = ""
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: datetime = Field(default_factory=datetime.utcnow)
    hold_time_minutes: float = 0.0


# ===== Modelli Risposte AI =====

class KeyLevels(BaseModel):
    """Livelli chiave di supporto e resistenza."""
    support: list[float] = Field(default_factory=list)
    resistance: list[float] = Field(default_factory=list)


class AITradeStrategy(BaseModel):
    """Strategia di trading suggerita dall'AI."""
    action: TradeAction
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size_oz: float = 0.0
    urgency: Urgency = Urgency.LOW
    market_sentiment: MarketSentiment = MarketSentiment.NEUTRAL
    key_levels: KeyLevels = Field(default_factory=KeyLevels)
    risk_reward_ratio: float = 0.0
    estimated_hold_time_minutes: int = 0


class AIPositionAdvice(BaseModel):
    """Consiglio AI sulla gestione di una posizione aperta."""
    action: PositionManagementAction
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    new_stop_loss: Optional[float] = None
    new_take_profit: Optional[float] = None


class AIEmergencyAssessment(BaseModel):
    """Valutazione AI su condizioni di emergenza."""
    continue_trading: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    recommended_action: EmergencyAction = EmergencyAction.CONTINUE


# ===== Modelli Portfolio =====

class AccountSummary(BaseModel):
    """Riepilogo account IBKR."""
    total_value: float = 0.0
    cash_balance: float = 0.0
    buying_power: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl_today: float = 0.0
    margin_used: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Portfolio(BaseModel):
    """Stato completo del portfolio."""
    account: AccountSummary = Field(default_factory=AccountSummary)
    positions: list[Position] = Field(default_factory=list)
    pending_orders: list[Order] = Field(default_factory=list)
    daily_trades: list[TradeRecord] = Field(default_factory=list)
    daily_pnl: float = 0.0
    trades_count_today: int = 0
    win_rate_today: float = 0.0
    last_sync: datetime = Field(default_factory=datetime.utcnow)


# ===== Modelli Notifiche =====

class TradeNotification(BaseModel):
    """Payload notifica per tradeBotNotify."""
    bot_name: str = "AI-Trading-Bot"
    symbol: str
    action: str
    quantity: float
    price: float
    pnl: Optional[float] = None
    ai_confidence: float = 0.0
    reasoning: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ===== Modelli API Response =====

class HealthResponse(BaseModel):
    """Risposta endpoint health check."""
    status: str = "ok"
    version: str = "0.1.0"
    environment: str = "development"
    trading_enabled: bool = False
    uptime_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StatusResponse(BaseModel):
    """Risposta endpoint status completo."""
    health: HealthResponse
    portfolio: Optional[Portfolio] = None
    ibkr_connected: bool = False
    ai_engine_ready: bool = False
    last_analysis: Optional[datetime] = None
    next_analysis: Optional[datetime] = None


# Aggiornamento forward refs per modelli con riferimenti circolari
MarketContext.model_rebuild()
