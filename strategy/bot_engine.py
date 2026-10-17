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
from utils.helpers import market_analysis_allowed
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
        self._market_closed_logged: set[str] = set()

    async def _load_market_hours(self) -> dict[str, Any]:
        """Carica la configurazione degli orari di mercato salvata."""
        return {
            "enabled": await self.db.get_config("market_hours_enabled", True),
            "timezone": await self.db.get_config("market_hours_timezone", "Europe/Rome"),
            "weekdays": await self.db.get_config("market_hours_weekdays", "mon,tue,wed,thu,fri"),
            "open_time": await self.db.get_config("market_hours_open_time", "15:30"),
            "close_time": await self.db.get_config("market_hours_close_time", "22:00"),
            "pre_open_minutes": int(await self.db.get_config("market_hours_pre_open_minutes", 10)),
        }

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
                    # 0. Applica le condizioni di orario di mercato configurate
                    market_cfg = await self._load_market_hours()
                    allowed, reason = market_analysis_allowed(market_cfg)
                    if not allowed:
                        if sym not in self._market_closed_logged:
                            self._market_closed_logged.add(sym)
                            await self.db.log_bot_event(
                                symbol=sym,
                                level="INFO",
                                message=f"Mercato chiuso: {reason}. In attesa della finestra pre-apertura configurata.",
                                metadata={"market_hours": market_cfg, "reason": reason},
                            )
                        await asyncio.sleep(60)
                        continue
                    else:
                        if sym in self._market_closed_logged:
                            self._market_closed_logged.discard(sym)
                            await self.db.log_bot_event(
                                symbol=sym,
                                level="INFO",
                                message=f"Mercato aperto: analisi e decisioni riattivate secondo la configurazione orari.",
                                metadata={"market_hours": market_cfg},
                            )

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
                        # Calcola se la posizione esistente (reale o simulata) copre già il budget
                        existing_val = (existing_pos.market_value if existing_pos and existing_pos.market_value > 0
                                        else ((existing_pos.quantity * current_price) if existing_pos else 0.0))
                        is_budget_exceeded = strategy.get("budget_saturated") or (existing_val + current_price > budget * 1.05) or (existing_pos is not None and existing_pos.quantity >= 1)

                        if is_budget_exceeded:
                            await self.db.log_bot_event(
                                symbol=sym,
                                level="INFO",
                                message=f"Ordine BUY inibito per rispetto del budget. La posizione presente ({existing_pos.quantity if existing_pos else 1} {strategy.get('unit', 'pz')}) copre già il budget di ${budget:,.2f}.",
                            )
                        else:
                            op_id = f"OP-{sym}-{int(datetime.now(timezone.utc).timestamp())}"
                            sl = strategy.get("stop_loss")
                            tp = strategy.get("take_profit")
                            unit = strategy.get("unit", "pz")
                            sec_type = existing_pos.sec_type if existing_pos else ("CFD" if sym == "XAUUSD" else "STK")
                            exchange = existing_pos.exchange if existing_pos else "SMART"
                            currency = existing_pos.currency if existing_pos else "USD"

                            order_result = await self.ib_client.place_market_order(
                                symbol=sym,
                                action="BUY",
                                quantity=float(size),
                                sec_type=sec_type,
                                exchange=exchange,
                                currency=currency,
                            )

                            if order_result.get("success"):
                                status = "EXECUTED"
                                details = f"Ordine reale BUY eseguito su IBKR (order_id: {order_result.get('order_id')}). {size} {unit}. Setup: {setup}. Motivo: {reasoning[:100]}..."
                                log_level = "SUCCESS"
                                log_msg = f"Operazione reale LONG (BUY) per {size} {unit} @ ~${current_price:.2f}. Ordine IBKR: {order_result.get('order_id')}. SL: ${sl} | TP: ${tp}."
                                simulated = False
                            else:
                                status = "FAILED"
                                details = f"Ordine BUY non eseguito: {order_result.get('error')}. Nessuna operazione effettuata."
                                log_level = "ERROR"
                                log_msg = f"Ordine BUY NON eseguito su {sym}: {order_result.get('error')}"
                                simulated = False

                            await self.db.record_executed_operation(
                                operation_id=op_id,
                                symbol=sym,
                                operation_type="LONG",
                                action="BUY",
                                quantity=float(size),
                                price=float(current_price),
                                stop_loss=float(sl) if sl else None,
                                take_profit=float(tp) if tp else None,
                                pnl=0.0,
                                status=status,
                                details=details,
                            )
                            await self.db.log_bot_event(
                                symbol=sym,
                                level=log_level,
                                message=log_msg,
                                metadata={"operation_id": op_id, "action": "BUY", "type": "LONG", "price": current_price, "size": size, "simulated": simulated, "order_id": order_result.get("order_id"), "order_status": status},
                            )
                    elif action in ("SELL", "CLOSE"):
                        op_type = "CLOSE_LONG" if (existing_pos and existing_pos.direction.value.upper() == "LONG") else "SHORT"
                        sl = strategy.get("stop_loss")
                        tp = strategy.get("take_profit")
                        unit = strategy.get("unit", "pz")
                        pnl_val = existing_pos.unrealized_pnl if existing_pos else 0.0
                        sec_type = existing_pos.sec_type if existing_pos else ("CFD" if sym == "XAUUSD" else "STK")
                        exchange = existing_pos.exchange if existing_pos else "SMART"
                        currency = existing_pos.currency if existing_pos else "USD"

                        # Evita doppioni reali: se su IBKR esiste già un ordine SELL aperto,
                        # rispetta quello e non ne vengono aggiunti altri.
                        open_orders = await self.ib_client.get_open_orders(sym)
                        open_sell_orders = [o for o in open_orders if (o.get("action") or "").upper() == "SELL"]
                        if open_sell_orders:
                            await self.db.log_bot_event(
                                symbol=sym,
                                level="INFO",
                                message=f"Ordine SELL già presente su IBKR ({open_sell_orders[0].get('order_id')}). Non vengono aggiunti altri ordini di vendita.",
                                metadata={"open_sell_orders": open_sell_orders},
                            )
                            continue

                        # Se esiste già un ordine SELL pendente registrato, verifica lo stato su IBKR
                        # senza crearne un altro (evita doppioni di vendita in attesa di esecuzione).
                        pending_ops = await self.db.get_pending_operations(sym)
                        existing_pending = pending_ops[0] if pending_ops else None

                        if existing_pending and existing_pending.get("order_id"):
                            ib_status_info = await self.ib_client.get_order_status(existing_pending["order_id"])
                            ib_status = ib_status_info.get("status", "Unknown")
                            if ib_status_info.get("filled") or ib_status == "Filled":
                                await self.db.record_executed_operation(
                                    operation_id=existing_pending["operation_id"],
                                    symbol=sym,
                                    operation_type=op_type,
                                    action=action,
                                    quantity=float(size),
                                    price=float(current_price),
                                    stop_loss=float(sl) if sl else None,
                                    take_profit=float(tp) if tp else None,
                                    pnl=float(pnl_val),
                                    status="EXECUTED",
                                    details=f"Ordine SELL pendente ora eseguito su IBKR (order_id: {existing_pending['order_id']}). PnL: ${pnl_val:+.2f}.",
                                )
                                await self.db.log_bot_event(
                                    symbol=sym,
                                    level="WARNING",
                                    message=f"Ordine SELL pendente ora eseguito su IBKR (order_id: {existing_pending['order_id']}). PnL: ${pnl_val:+.2f}.",
                                    metadata={"operation_id": existing_pending["operation_id"], "action": action, "type": op_type, "order_id": existing_pending["order_id"], "order_status": "EXECUTED"},
                                )
                            else:
                                await self.db.log_bot_event(
                                    symbol=sym,
                                    level="INFO",
                                    message=f"Ordine SELL già pendente su IBKR (order_id: {existing_pending['order_id']}, stato: {ib_status}). In attesa di esecuzione.",
                                    metadata={"operation_id": existing_pending["operation_id"], "action": action, "type": op_type, "order_id": existing_pending["order_id"], "order_status": ib_status},
                                )
                        else:
                            op_id = f"PENDING-{sym}-SELL"
                            order_result = await self.ib_client.place_market_order(
                                symbol=sym,
                                action="SELL",
                                quantity=float(size),
                                sec_type=sec_type,
                                exchange=exchange,
                                currency=currency,
                            )

                            if order_result.get("success"):
                                status = "EXECUTED"
                                details = f"Ordine reale {action} eseguito su IBKR (order_id: {order_result.get('order_id')}). {size} {unit}. Setup: {setup}. PnL: ${pnl_val:+.2f}."
                                log_level = "WARNING"
                                log_msg = f"Operazione reale {op_type} ({action}) su {sym} eseguita su IBKR. Ordine: {order_result.get('order_id')}. PnL: ${pnl_val:+.2f}."
                                simulated = False
                            elif order_result.get("status") in ("Submitted", "PendingSubmit", "PreSubmit"):
                                status = "PENDING"
                                details = f"Ordine SELL inviato a IBKR in attesa di esecuzione (order_id: {order_result.get('order_id')}). Mercato chiuso o ordine non ancora riempito."
                                log_level = "INFO"
                                log_msg = f"Ordine SELL pendente su {sym} (order_id: {order_result.get('order_id')}). In attesa di esecuzione su IBKR."
                                simulated = False
                            else:
                                status = "FAILED"
                                details = f"Ordine {action} non eseguito: {order_result.get('error')}. Nessuna operazione effettuata."
                                log_level = "ERROR"
                                log_msg = f"Ordine {action} NON eseguito su {sym}: {order_result.get('error')}"
                                simulated = False

                            await self.db.record_executed_operation(
                                operation_id=op_id,
                                symbol=sym,
                                operation_type=op_type,
                                action=action,
                                quantity=float(size),
                                price=float(current_price),
                                stop_loss=float(sl) if sl else None,
                                take_profit=float(tp) if tp else None,
                                pnl=float(pnl_val),
                                status=status,
                                details=details,
                            )
                            await self.db.log_bot_event(
                                symbol=sym,
                                level=log_level,
                                message=log_msg,
                                metadata={"operation_id": op_id, "action": action, "type": op_type, "price": current_price, "size": size, "simulated": simulated, "order_id": order_result.get("order_id"), "order_status": status},
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
