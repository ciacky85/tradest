"""
utils/helpers.py - Funzioni di utilità generiche.

Raccolta di helper functions usate in tutta l'applicazione:
formattazione, timestamp, calcoli, validazioni.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from dateutil import tz


def utc_now() -> datetime:
    """Restituisce il timestamp corrente in UTC timezone-aware."""
    return datetime.now(timezone.utc)


def now_rome() -> datetime:
    """Restituisce il timestamp corrente nel fuso orario Europe/Rome."""
    rome_tz = tz.gettz("Europe/Rome")
    return datetime.now(rome_tz)


def is_trading_hours(
    start_hour: int = 8,
    end_hour: int = 22,
    timezone_str: str = "Europe/Rome",
) -> bool:
    """
    Verifica se siamo in orario di trading.

    Args:
        start_hour: Ora di apertura (default 08:00).
        end_hour: Ora di chiusura (default 22:00).
        timezone_str: Fuso orario di riferimento.

    Returns:
        True se siamo in orario di trading.
    """
    local_tz = tz.gettz(timezone_str)
    now = datetime.now(local_tz)
    return start_hour <= now.hour < end_hour and now.weekday() < 5  # Lun-Ven


def market_analysis_allowed(market_cfg: dict[str, Any]) -> tuple[bool, str]:
    """
    Verifica se in questo momento è consentito analizzare il mercato ed emettere ordini.

    Regola: l'analisi deve avvenire poco prima dell'apertura (open_time - pre_open_minutes)
    e rimanere consentita fino alla chiusura. Fuori da questa finestra non si analizza e non
    si emettono ordini.
    """
    if not market_cfg.get("enabled", True):
        return True, ""

    tz_name = market_cfg.get("timezone", "Europe/Rome")
    weekdays_raw = market_cfg.get("weekdays", "mon,tue,wed,thu,fri")
    weekdays = {d.strip().lower()[:3] for d in str(weekdays_raw).split(",") if d.strip()}

    try:
        local_tz = tz.gettz(tz_name) or tz.gettz("Europe/Rome")
    except Exception:
        local_tz = tz.gettz("Europe/Rome")

    now = datetime.now(local_tz)
    day = now.strftime("%a").lower()
    if day not in weekdays:
        return False, f"mercato chiuso ({now.strftime('%A')})"

    try:
        open_dt = datetime.strptime(market_cfg.get("open_time", "15:30"), "%H:%M")
        close_dt = datetime.strptime(market_cfg.get("close_time", "22:00"), "%H:%M")
        open_minutes = open_dt.hour * 60 + open_dt.minute
        close_minutes = close_dt.hour * 60 + close_dt.minute
        pre_open = int(market_cfg.get("pre_open_minutes", 10))
    except (TypeError, ValueError):
        return True, ""

    start_minutes = max(0, open_minutes - pre_open)
    now_minutes = now.hour * 60 + now.minute

    if start_minutes <= now_minutes <= close_minutes:
        return True, ""
    return False, f"fuori orario (finestra {market_cfg.get('open_time', '15:30')} - {market_cfg.get('close_time', '22:00')}, pre-analisi {pre_open} min)"


def format_currency(amount: float, currency: str = "USD") -> str:
    """
    Formatta un importo come stringa valuta.

    Args:
        amount: Importo numerico.
        currency: Codice valuta (default USD).

    Returns:
        Stringa formattata (es: "$1,234.56").
    """
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    symbol = symbols.get(currency, currency + " ")
    if amount < 0:
        return f"-{symbol}{abs(amount):,.2f}"
    return f"{symbol}{amount:,.2f}"


def format_pct(value: float, decimals: int = 2) -> str:
    """
    Formatta un valore come percentuale.

    Args:
        value: Valore numerico (es: 0.05 per 5%).
        decimals: Numero di decimali.

    Returns:
        Stringa formattata (es: "+5.00%").
    """
    pct = value * 100
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.{decimals}f}%"


def round_price(price: float, tick_size: float = 0.01) -> float:
    """
    Arrotonda un prezzo al tick size più vicino.

    Args:
        price: Prezzo da arrotondare.
        tick_size: Dimensione minima del tick.

    Returns:
        Prezzo arrotondato.
    """
    d_price = Decimal(str(price))
    d_tick = Decimal(str(tick_size))
    return float((d_price / d_tick).quantize(Decimal("1"), ROUND_HALF_UP) * d_tick)


def calculate_pnl(
    entry_price: float,
    current_price: float,
    quantity: float,
    direction: str = "long",
) -> float:
    """
    Calcola il P&L di una posizione.

    Args:
        entry_price: Prezzo di entrata.
        current_price: Prezzo corrente.
        quantity: Quantità.
        direction: "long" o "short".

    Returns:
        Profitto/perdita in USD.
    """
    if direction.lower() == "short":
        return (entry_price - current_price) * quantity
    return (current_price - entry_price) * quantity


def calculate_stop_loss(
    entry_price: float,
    stop_pct: float,
    direction: str = "long",
) -> float:
    """
    Calcola il prezzo di stop-loss.

    Args:
        entry_price: Prezzo di entrata.
        stop_pct: Percentuale di stop (es: 0.005 per 0.5%).
        direction: "long" o "short".

    Returns:
        Prezzo di stop-loss.
    """
    if direction.lower() == "short":
        return round_price(entry_price * (1 + stop_pct))
    return round_price(entry_price * (1 - stop_pct))


def calculate_take_profit(
    entry_price: float,
    tp_pct: float,
    direction: str = "long",
) -> float:
    """
    Calcola il prezzo di take-profit.

    Args:
        entry_price: Prezzo di entrata.
        tp_pct: Percentuale di take-profit (es: 0.01 per 1%).
        direction: "long" o "short".

    Returns:
        Prezzo di take-profit.
    """
    if direction.lower() == "short":
        return round_price(entry_price * (1 - tp_pct))
    return round_price(entry_price * (1 + tp_pct))


def generate_trade_id() -> str:
    """Genera un ID univoco per un trade."""
    return f"TRD-{uuid.uuid4().hex[:12].upper()}"


def generate_order_id() -> str:
    """Genera un ID univoco per un ordine."""
    return f"ORD-{uuid.uuid4().hex[:12].upper()}"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divisione sicura che restituisce default se il denominatore è zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Limita un valore tra min e max."""
    return max(min_val, min(value, max_val))


def dict_hash(d: dict[str, Any]) -> str:
    """Genera un hash MD5 di un dizionario (per dedup/cache)."""
    import json
    serialized = json.dumps(d, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()
