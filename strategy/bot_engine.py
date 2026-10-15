"""
strategy/bot_engine.py - Motore di esecuzione continua e parallela dei bot di trading per simbolo.

Caratteristiche:
- Esecuzione in background (Task asyncio indipendenti per ciascun simbolo attivo).
- Persistenza dello stato su SQLite: se l'utente chiude il browser o cambia computer, i bot continuano ad operare.
- Logging persistente verboso su database (consultabile in qualsiasi momento filtrando per simbolo).
- Ciclo di scalping continuo:
  1. Verifica portafoglio reale IBKR e saturazione budget per il titolo
  2. Snapshot di mercato corrente (prezzo, spread, indicatori tecnici)
  3. Valutazione AI della strategia e generazione decisioni
  4. Registrazione dettagliata degli eventi
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import get_settings
from data.database import get_db
from data.market_analyzer import get_market_analyzer
from integration.ibkr_client import get_ibkr_client
from strategy.scalping_strategy import get_scalping_manager
from utils.logger import get_logger

logger = get_logger("bot_engine")


class MultiBotEngine:
    """Gestore dei bot di trading paralleli per ciascun simbolo."""

    def __init__(self) -> None:
        self.active_tasks: dict[str, asyncio.Task] = {}
        self.scalping_mgr = get_scalping_manager()
        self.market_analyzer = get_market_analyzer()
        self.ib_client = get_ibkr_client()
        self.db = get_db()
        self._lock = asyncio.Lock()

    async def initialize_from_db(self) -> None:
        """Al riavvio del server, riattiva i bot che erano marcati come attivi."""
        active_bots = await self.db.get_config("active_trading_bots", {})
        for sym, is_active in active_bots.items():
            if is_active and sym not in self.active_tasks:
                self.start_symbol_bot(sym)

    def is_bot_active(self, symbol: str) -> bool:
        """Verifica se il bot per il simbolo specificato è attualmente in esecuzione."""
        sym = symbol.upper().strip()
        task = self.active_tasks.get(sym)
        return task is not None and not task.done()

    def get_all_bots_status(self) -> dict[str, bool]:
        """Restituisce lo stato di tutti i bot per ciascun simbolo."""
        symbols = ["XAUUSD", "NVDA", "SPCX", "IB1T"]
        return {s: self.is_bot_active(s) for s in symbols}

    def start_symbol_bot(self, symbol: str) -> bool:
        """Avvia il task in background per il trading del simbolo specificato."""
        sym = symbol.upper().strip()
        if self.is_bot_active(sym):
            return True

        task = asyncio.create_task(self._bot_loop(sym), name=f"bot_loop_{sym}")
        self.active_tasks[sym] = task
        logger.info(f"Bot avviato in background per {sym}")
        return True

    async def stop_symbol_bot(self, symbol: str) -> bool:
        """Arresta il task in background per il simbolo specificato."""
        sym = symbol.upper().strip()
        task = self.active_tasks.get(sym)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.active_tasks.pop(sym, None)

        # Aggiorna lo stato nel DB
        active_bots = await self.db.get_config("active_trading_bots", {})
        active_bots[sym] = False
        await self.db.set_config("active_trading_bots", active_bots)

        await self.db.log_bot_event(
            symbol=sym,
            level="INFO",
            message=f"Bot di trading per {sym} arrestato dall'utente. Nessuna nuova operazione verrà aperta.",
        )
        logger.info(f"Bot arrestato per {sym}")
        return True

    async def _bot_loop(self, symbol: str) -> None:
        """Loop continuo del bot per il singolo strumento finanziario."""
        sym = symbol.upper().strip()

        # Segna come attivo nel DB
        active_bots = await self.db.get_config("active_trading_bots", {})
        active_bots[sym] = True
        await self.db.set_config("active_trading_bots", active_bots)

        budget = await self.scalping_mgr.get_symbol_budget(sym)
        await self.db.log_bot_event(
            symbol=sym,
            level="SUCCESS",
            message=f"Avvio ciclo di trading continuo su {sym}. Budget allocato: ${budget:,.2f}. Modalità: Scalping.",
            metadata={"budget": budget},
        )

        loop_count = 0
        try:
            while True:
                loop_count += 1
                try:
                    # 1. Verifica Portafoglio Reale
                    portfolio = await self.ib_client.get_portfolio()
                    existing_pos = None
                    for p in portfolio.positions:
                        if p.symbol.upper() == sym or (sym == "XAUUSD" and p.symbol.upper() in ("XAUUSD", "GOLD")):
                            existing_pos = p
                            break

                    pos_desc = (
                        f"{existing_pos.direction.value.upper()} {existing_pos.quantity} pz/oz @ ${existing_pos.entry_price:.2f} (P&L: ${existing_pos.unrealized_pnl:+.2f})"
                        if existing_pos
                        else "Nessuna posizione aperta"
                    )

                    # 2. Snapshot di mercato corrente
                    mkt = await self.market_analyzer.get_symbol_analysis(sym)
                    current_price = mkt.current_price

                    await self.db.log_bot_event(
                        symbol=sym,
                        level="INFO",
                        message=(
                            f"[Ciclo #{loop_count}] Prezzo: ${current_price:.2f} | Spread: ${mkt.spread:.2f} | "
                            f"RSI: {mkt.indicators.rsi} | Posizione Portafoglio: {pos_desc}"
                        ),
                        metadata={"price": current_price, "rsi": mkt.indicators.rsi, "has_position": bool(existing_pos)},
                    )

                    # 3. Analisi e decisione strategica tramite AI
                    strategy = await self.scalping_mgr.analyze_and_generate_strategy(symbol=sym)
                    action = strategy.get("action", "HOLD")
                    confidence = strategy.get("confidence", 0.0)
                    reasoning = strategy.get("reasoning", "")
                    setup = strategy.get("scalping_setup", "")
                    size = strategy.get("position_size", 1)

                    log_level = "WARNING" if action in ("BUY", "SELL", "CLOSE") else "INFO"
                    await self.db.log_bot_event(
                        symbol=sym,
                        level=log_level,
                        message=(
                            f"Decisione AI: {action} (Confidenza: {int(confidence*100)}%) - Size: {size} {strategy.get('unit', '')} | "
                            f"Setup: {setup} | Ragionamento: {reasoning}"
                        ),
                        metadata=strategy,
                    )

                    if action == "BUY":
                        if strategy.get("budget_saturated"):
                            await self.db.log_bot_event(
                                symbol=sym,
                                level="INFO",
                                message=f"Ordine BUY inibito per rispetto del budget. La posizione esistente copre già il budget di ${budget:,.2f}.",
                            )
                        else:
                            await self.db.log_bot_event(
                                symbol=sym,
                                level="SUCCESS",
                                message=f"Segnale operativo BUY generato per {size} {strategy.get('unit')} @ ~${current_price:.2f}. SL: ${strategy.get('stop_loss')} | TP: ${strategy.get('take_profit')}.",
                            )
                    elif action in ("SELL", "CLOSE"):
                        await self.db.log_bot_event(
                            symbol=sym,
                            level="WARNING",
                            message=f"Segnale operativo SELL/CLOSE per liquidare posizione esistente o aprire short. Budget verrà liberato ed espanso per rientro.",
                        )
                    else:
                        await self.db.log_bot_event(
                            symbol=sym,
                            level="INFO",
                            message=f"Condizioni di scalping in attesa (HOLD). Monitoraggio attivo livelli supporto/resistenza.",
                        )

                except Exception as e:
                    logger.error(f"Errore nel ciclo di trading per {sym}", exc=str(e))
                    await self.db.log_bot_event(
                        symbol=sym,
                        level="ERROR",
                        message=f"Errore durante il ciclo di scalping: {str(e)}",
                    )

                # Attesa intervallo tra i cicli di scalping (30 secondi configurabili)
                await asyncio.sleep(30)

        except asyncio.CancelledError:
            logger.info(f"Task del bot per {sym} cancellato")
        finally:
            active_bots = await self.db.get_config("active_trading_bots", {})
            active_bots[sym] = False
            await self.db.set_config("active_trading_bots", active_bots)


_bot_engine: Optional[MultiBotEngine] = None


def get_bot_engine() -> MultiBotEngine:
    global _bot_engine
    if _bot_engine is None:
        _bot_engine = MultiBotEngine()
    return _bot_engine
