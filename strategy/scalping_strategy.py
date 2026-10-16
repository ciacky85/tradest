"""
strategy/scalping_strategy.py - Gestore strategico di scalping multirisorsa con controllo budget e quote intere.

Regole operative fondamentali:
1. Controllo Quote Intere (No frazioni):
   - Interactive Brokers non accetta frazioni di contratto/oncia. La size calcolata viene sempre arrotondata per difetto all'intero: math.floor(budget / current_price).
2. Priorità al Portafoglio Esistente & Limite di Budget:
   - Se il portafoglio possiede già una posizione sul titolo (es. 1 oz @ $4157) che copre o satura il budget stabilito (es. budget $5000):
     * È TASSATIVAMENTE VIETATO effettuare ulteriori acquisti (NO BUY).
     * L'AI può solo gestire la posizione esistente (HOLD) o chiuderla/alleggerirla (SELL / CLOSE).
   - Se la posizione viene chiusa/venduta, il budget viene liberato ed espanso, consentendo alla successiva analisi di decidere se rientrare (in LONG oppure SHORT) sfruttando il capitale libero.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import get_settings, load_ai_prompts, load_trading_params
from data.database import get_db
from data.market_analyzer import MarketHistoricalContext, get_market_analyzer
from integration.gemini_client import get_gemini_client
from integration.ibkr_client import get_ibkr_client
from utils.logger import get_logger

logger = get_logger("scalping_strategy")


class ScalpingStrategyManager:
    """Orchestratore della strategia di scalping con vincoli di portafoglio e budget."""

    def __init__(self) -> None:
        self.market_analyzer = get_market_analyzer()
        self.ai_client = get_gemini_client()
        self.ib_client = get_ibkr_client()

    async def get_symbol_budget(self, symbol: str) -> float:
        """Recupera il budget allocato per il simbolo (da SQLite runtime o da configurazione)."""
        db = get_db()
        custom_budgets = await db.get_config("symbols_budget", {})
        if symbol.upper() in custom_budgets:
            return float(custom_budgets[symbol.upper()])

        # Fallback da trading_params.json
        t_params = load_trading_params()
        asset_cfg = t_params.get("assets", {}).get(symbol.upper(), {})
        return float(asset_cfg.get("risk_management", {}).get("max_budget_per_trade_usd", 5000.0))

    async def set_symbol_budget(self, symbol: str, budget: float) -> None:
        """Salva il budget personalizzato per un simbolo in SQLite."""
        db = get_db()
        custom_budgets = await db.get_config("symbols_budget", {})
        custom_budgets[symbol.upper()] = float(budget)
        await db.set_config("symbols_budget", custom_budgets)

    async def analyze_and_generate_strategy(
        self,
        symbol: str = "XAUUSD",
        custom_budget: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Esegue l'analisi completa per il simbolo scelto tenendo conto del budget e del portafoglio reale.
        """
        sym = symbol.upper().strip()

        # 1. Recupera o salva il budget per il simbolo
        if custom_budget is not None and custom_budget > 0:
            await self.set_symbol_budget(sym, custom_budget)
            target_budget = float(custom_budget)
        else:
            target_budget = await self.get_symbol_budget(sym)

        # 2. Sincronizzazione preventiva Portafoglio IBKR
        try:
            if not self.ib_client.is_connected:
                await self.ib_client.connect(timeout=5.0)
        except Exception as e:
            logger.warning("Connessione preventiva a IBKR non disponibile", exc=str(e))

        portfolio = await self.ib_client.get_portfolio()
        acc = portfolio.account

        # 3. Controllo della posizione esistente per il simbolo
        existing_pos = None
        for p in portfolio.positions:
            if p.symbol.upper() == sym or (sym == "XAUUSD" and p.symbol.upper() in ("XAUUSD", "GOLD")):
                existing_pos = p
                break

        existing_qty = float(existing_pos.quantity) if existing_pos else 0.0
        existing_value = float(existing_pos.market_value) if existing_pos else 0.0
        existing_pnl = float(existing_pos.unrealized_pnl) if existing_pos else 0.0

        if existing_pos:
            dir_str = getattr(existing_pos.direction, "value", str(existing_pos.direction)).upper()
            pos_desc = (
                f"ATTUALMENTE APERTA: {dir_str} {existing_qty} pz/oz @ ${existing_pos.entry_price:.2f} "
                f"(Valore Mercato: ${existing_value:,.2f}, P&L Non Realizzato: ${existing_pnl:+.2f})"
            )
        else:
            pos_desc = f"NESSUNA POSIZIONE APERTA su {sym} (Esposizione 0)."

        # 4. Analisi di Mercato (30 giorni, 7 giorni e indicatori tecnici)
        mkt: MarketHistoricalContext = await self.market_analyzer.get_symbol_analysis(sym)
        current_price = mkt.current_price

        # 5. Calcolo Quote Intere (No frazioni) e Capienza Budget
        # Es. Se prezzo = $4100 e budget = $5000 -> max_shares_in_budget = 1
        max_shares_in_budget = math.floor(target_budget / current_price) if current_price > 0 else 0

        # Verifica se la posizione esistente già copre o satura il budget
        # Se già abbiamo quote >= max_shares_in_budget, il budget per nuovi acquisti è esaurito!
        budget_saturated = False
        remaining_budget = max(0.0, target_budget - existing_value)
        shares_can_buy = math.floor(remaining_budget / current_price) if current_price > 0 else 0

        if existing_value >= target_budget or shares_can_buy <= 0:
            budget_saturated = True

        # Direttiva per l'AI
        if existing_pos and budget_saturated:
            ai_budget_directive = (
                f"ATTENZIONE: Il portafoglio possiede già una posizione su {sym} ({existing_qty} {mkt.unit} per un valore di ${existing_value:,.2f}) "
                f"che SODDISFA O SUPERA IL BUDGET DEFINITO (${target_budget:,.2f}). "
                f"È ASSOLUTAMENTE VIETATO consigliare l'azione 'BUY' per ulteriori acquisti. "
                f"Puoi consigliare SOLO: 'HOLD' per mantenere la posizione esistente, oppure 'SELL' / 'CLOSE' per chiuderla/liquidarla in profitto o stop loss. "
                f"Se consiglierai 'SELL', il budget verrà liberato e consentirà in seguito di rientrare (in LONG o SHORT)."
            )
        elif existing_pos and not budget_saturated:
            ai_budget_directive = (
                f"Il portafoglio ha una posizione su {sym} di {existing_qty} {mkt.unit} (${existing_value:,.2f}). "
                f"Il budget residuo consente al massimo di acquistare altri {shares_can_buy} {mkt.unit} interi (quote frazionate NON ammesse da IBKR). "
                f"Valuta se fare BUY (max {shares_can_buy}), HOLD o SELL."
            )
        else:
            if max_shares_in_budget <= 0:
                ai_budget_directive = (
                    f"Il budget impostato (${target_budget:,.2f}) è inferiore al prezzo di 1 singola quota intera (${current_price:,.2f}). "
                    f"Non è possibile acquistare quote intere. Consiglia HOLD."
                )
            else:
                ai_budget_directive = (
                    f"Nessuna posizione aperta su {sym}. Con un budget di ${target_budget:,.2f} e prezzo corrente di ${current_price:,.2f}, "
                    f"la quantità intera acquistabile è esattamente di {max_shares_in_budget} {mkt.unit} (arrotondato per difetto, no frazioni). "
                    f"Valuta se entrare con BUY, SELL (se short consentito) o attendere in HOLD."
                )

        # 6. Compilazione Prompt
        prompts = load_ai_prompts()
        ma_prompt = prompts.get("prompts", {}).get("market_analysis", {})
        sys_instruction = ma_prompt.get("system_instruction", "")
        template = ma_prompt.get("analysis_template", "")

        context_vars = {
            "symbol": sym,
            "trend_30d": str(mkt.trend_30d),
            "low_30d": f"{mkt.low_30d:.2f}",
            "high_30d": f"{mkt.high_30d:.2f}",
            "change_pct_30d": f"{mkt.change_pct_30d:+.2f}",
            "trend_7d": str(mkt.trend_7d),
            "low_7d": f"{mkt.low_7d:.2f}",
            "high_7d": f"{mkt.high_7d:.2f}",
            "change_pct_7d": f"{mkt.change_pct_7d:+.2f}",
            "supports": ", ".join([f"${s:.1f}" for s in mkt.supports]),
            "resistances": ", ".join([f"${r:.1f}" for r in mkt.resistances]),
            "current_price": f"{mkt.current_price:.2f}",
            "bid": f"{mkt.bid:.2f}",
            "ask": f"{mkt.ask:.2f}",
            "spread": f"{mkt.spread:.2f}",
            "volume": f"{mkt.volume:.1f}",
            "daily_change_pct": f"{mkt.daily_change_pct:+.2f}",
            "rsi": f"{mkt.indicators.rsi:.1f}",
            "ema_fast": f"{mkt.indicators.ema_fast:.2f}",
            "ema_slow": f"{mkt.indicators.ema_slow:.2f}",
            "macd": f"{mkt.indicators.macd:.2f}",
            "macd_signal": f"{mkt.indicators.macd_signal:.2f}",
            "macd_hist": f"{mkt.indicators.macd_hist:.2f}",
            "atr": f"{mkt.indicators.atr:.2f}",
            "bb_upper": f"{mkt.indicators.bb_upper:.2f}",
            "bb_middle": f"{mkt.indicators.bb_middle:.2f}",
            "bb_lower": f"{mkt.indicators.bb_lower:.2f}",
            "portfolio_total_value": f"{acc.total_value:,.2f}",
            "portfolio_cash": f"{acc.cash_balance:,.2f}",
            "portfolio_buying_power": f"{acc.buying_power:,.2f}",
            "open_positions": pos_desc,
            "recent_trades": "Operatività scalping sincronizzata su IBKR",
            "daily_pnl": f"{portfolio.daily_pnl:+.2f}",
            "trades_today": "0",
            "win_rate_today": "0.0",
            "max_budget": f"{target_budget:,.2f}",
            "max_position_size": str(max(1, max_shares_in_budget)),
            "stop_loss_pct": "0.5",
            "take_profit_pct": "1.0",
            "allowed_direction": "both",
        }

        filled_prompt = template
        for key, val in context_vars.items():
            filled_prompt = filled_prompt.replace(f"{{{{{key}}}}}", str(val))
            filled_prompt = filled_prompt.replace(f"{{{key}}}", str(val))

        # Aggiunta istruzioni di vincolo budget e portafoglio all'AI
        filled_prompt += f"""

## VINCOLI DI PORTAFOGLIO & GESTIONE BUDGET (TASSATIVI):
- Posizione su {sym}: {pos_desc}
- Budget totale allocato per {sym}: ${target_budget:,.2f}
- Valore posizione esistente: ${existing_value:,.2f}
- Prezzo corrente quota: ${current_price:,.2f}
- Quantità massima intera consentita dal budget: {max_shares_in_budget} {mkt.unit}
- DIRETTIVA RIGIDA: {ai_budget_directive}
- NOTA INTERI: Su IBKR le quantità DEVONO ESSERE INTERE (1, 2, 3... quote). Mai indicare numeri frazionari (es. 1.5, 0.8).
"""

        # 7. Interrogazione AI
        ai_result = await self.ai_client.generate_trade_analysis(
            prompt=filled_prompt,
            system_instruction=sys_instruction,
        )

        # 8. Sanificazione dell'Azione (Guardia di Rischio sul Budget)
        raw_action = str(ai_result.get("action", "HOLD")).upper()
        # Se il portafoglio ha già saturato il budget e l'AI propone BUY, forziamo HOLD
        if budget_saturated and existing_pos and raw_action == "BUY":
            logger.warning(
                f"Guardia di rischio attivata: {sym} ha già saturato il budget (${existing_value:,.2f} >= ${target_budget:,.2f}). Azione BUY forzata a HOLD."
            )
            raw_action = "HOLD"
            reasoning = (
                f"Budget di ${target_budget:,.2f} già completamente allocato sulla posizione esistente ({existing_qty} {mkt.unit} @ ${existing_pos.entry_price:.2f}). "
                f"Nessun ulteriore acquisto consentito. Mantenimento (HOLD) in attesa di target profit o stop loss."
            )
        else:
            reasoning = ai_result.get("reasoning", "Analisi completata con successo")

        # Size intera
        suggested_size = ai_result.get("position_size_oz") or ai_result.get("position_size") or max_shares_in_budget
        try:
            integer_size = max(1, math.floor(float(suggested_size)))
        except Exception:
            integer_size = max(1, max_shares_in_budget)

        if not existing_pos and max_shares_in_budget > 0:
            integer_size = min(integer_size, max_shares_in_budget)
        elif existing_pos:
            integer_size = int(existing_qty) if raw_action in ("SELL", "CLOSE", "HOLD") else max(1, shares_can_buy)

        entry_price = float(ai_result.get("entry_price") or current_price)
        stop_loss = float(ai_result.get("stop_loss") or (round(entry_price * 0.995, 2) if raw_action == "BUY" else round(entry_price * 1.005, 2)))
        take_profit = float(ai_result.get("take_profit") or (round(entry_price * 1.01, 2) if raw_action == "BUY" else round(entry_price * 0.99, 2)))

        strategy_payload = {
            "symbol": sym,
            "action": raw_action,
            "confidence": float(ai_result.get("confidence", 0.75)),
            "reasoning": reasoning,
            "scalping_setup": ai_result.get("scalping_setup", "Gestione strategica budget e livelli tecnici"),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_size": integer_size,
            "position_size_oz": integer_size,
            "unit": mkt.unit,
            "budget": target_budget,
            "budget_saturated": budget_saturated,
            "urgency": ai_result.get("urgency", "MEDIUM"),
            "market_sentiment": ai_result.get("market_sentiment", "NEUTRAL"),
            "risk_reward_ratio": float(ai_result.get("risk_reward_ratio", 2.0)),
            "estimated_hold_time_minutes": int(ai_result.get("estimated_hold_time_minutes", 15)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "existing_position": {
                "has_position": bool(existing_pos),
                "details": pos_desc,
                "quantity": existing_qty,
                "market_value": existing_value,
                "unrealized_pnl": existing_pnl,
            },
            "historical_context": {
                "trend_30d": mkt.trend_30d,
                "range_30d": [mkt.low_30d, mkt.high_30d],
                "change_pct_30d": mkt.change_pct_30d,
                "trend_7d": mkt.trend_7d,
                "range_7d": [mkt.low_7d, mkt.high_7d],
                "change_pct_7d": mkt.change_pct_7d,
                "supports": mkt.supports,
                "resistances": mkt.resistances,
                "rsi": mkt.indicators.rsi,
                "ema_fast": mkt.indicators.ema_fast,
                "ema_slow": mkt.indicators.ema_slow,
            },
            "portfolio_context": {
                "account_id": acc.account_id,
                "total_value": acc.total_value,
                "cash": acc.cash_balance,
                "buying_power": acc.buying_power,
                "budget_per_trade": target_budget,
            },
        }

        # 9. Salvataggio in SQLite
        db = get_db()
        await db.set_config(f"active_strategy_{sym}", strategy_payload)
        await db.set_config("active_scalping_strategy", strategy_payload)
        await db.record_ai_decision(
            symbol=sym,
            action=raw_action,
            confidence=strategy_payload["confidence"],
            reasoning=reasoning,
            market_sentiment=strategy_payload["market_sentiment"],
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_oz=float(integer_size),
            urgency=strategy_payload["urgency"],
            risk_reward_ratio=strategy_payload["risk_reward_ratio"],
            executed=0,
            rejection_reason="Definizione strategia multirisorsa completata",
        )

        return strategy_payload

    async def validate_auto_trading_readiness(
        self,
        symbol: str = "XAUUSD",
        force_fresh_analysis: bool = True,
    ) -> dict[str, Any]:
        """
        Sequenza obbligatoria pre-avvio del bot:
        1. Carica il portafoglio IBKR reale e aggiornato per verificare posizioni, liquidità e buying power.
        2. Esegue una NUOVA analisi AI fresca con snapshot di mercato in tempo reale (mai partire su dati obsoleti).
        3. Verifica i vincoli di budget e capienza prima di autorizzare l'avvio.
        """
        sym = symbol.upper().strip()
        db = get_db()

        # 1. Carica portafoglio reale IBKR aggiornato
        logger.info(f"Fase 1 Pre-Avvio Bot {sym}: caricamento portafoglio reale IBKR...")
        portfolio = await self.ib_client.get_portfolio()
        target_budget = await self.get_symbol_budget(sym)

        # 2. Lancia nuova analisi fresca di mercato e AI se richiesta (default True)
        if force_fresh_analysis:
            logger.info(f"Fase 2 Pre-Avvio Bot {sym}: esecuzione nuova analisi AI in tempo reale...")
            active_strategy = await self.analyze_and_generate_strategy(symbol=sym)
        else:
            active_strategy = await db.get_config(f"active_strategy_{sym}") or await db.get_config("active_scalping_strategy")

        if not active_strategy or active_strategy.get("symbol") != sym:
            return {
                "can_start": False,
                "reason": f"Impossibile definire una nuova strategia aggiornata per {sym}.",
            }

        # 3. Verifica capienza del buying power
        has_pos = any(p.symbol.upper() == sym or (sym == "XAUUSD" and p.symbol.upper() in ("XAUUSD", "GOLD")) for p in portfolio.positions)
        if not has_pos and portfolio.account.buying_power < target_budget and portfolio.account.cash_balance < 1000:
            return {
                "can_start": False,
                "reason": f"Buying power insufficiente (${portfolio.account.buying_power:,.2f}) per il budget di {sym} (${target_budget:,.2f}).",
            }

        return {
            "can_start": True,
            "strategy": active_strategy,
            "portfolio": portfolio.model_dump(),
            "account": {
                "account_id": portfolio.account.account_id,
                "cash": portfolio.account.cash_balance,
                "buying_power": portfolio.account.buying_power,
            },
        }


_strategy_manager: Optional[ScalpingStrategyManager] = None


def get_scalping_manager() -> ScalpingStrategyManager:
    global _strategy_manager
    if _strategy_manager is None:
        _strategy_manager = ScalpingStrategyManager()
    return _strategy_manager
