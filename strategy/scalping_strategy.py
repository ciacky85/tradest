"""
strategy/scalping_strategy.py - Gestore strategico di scalping su XAUUSD e controllo esecutivo del bot.

Caratteristiche:
- Priorità assoluta al Portafoglio IBKR reale:
  1. Connessione / Sincronizzazione con Interactive Brokers
  2. Verifica specifica della posizione esistente su XAUUSD (quantità, direzione, P&L, prezzo di carico)
  3. Controllo della disponibilità di buying power e rispetto del budget massimo per trade ($5,000)
- Analisi approfondita di mercato XAUUSD:
  * Trend macro 30 giorni e range
  * Focus ultima settimana (7 giorni)
  * Indicatori tecnici (EMA 9, EMA 21, RSI 14, MACD, ATR 14, Bollinger Bands) e pivot supporti/resistenze
- Compilazione sicura del prompt compatibile sia con marcatori {var} che {{var}}
- Interrogazione del motore AI (Omniroute / Gemini)
- Memorizzazione della strategia in SQLite e validazione per trading automatico.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import get_settings, load_ai_prompts, load_trading_params
from app.models import AITradeStrategy, TradeAction
from data.database import get_db
from data.market_analyzer import MarketHistoricalContext, get_market_analyzer
from integration.gemini_client import get_gemini_client
from integration.ibkr_client import get_ibkr_client
from utils.logger import get_logger

logger = get_logger("scalping_strategy")


class ScalpingStrategyManager:
    """Orchestratore della strategia di scalping su XAUUSD."""

    def __init__(self) -> None:
        self.market_analyzer = get_market_analyzer()
        self.ai_client = get_gemini_client()
        self.ib_client = get_ibkr_client()

    async def analyze_and_generate_strategy(self) -> dict[str, Any]:
        """
        Flusso Operativo:
        1. IMPORTAZIONE PREVENTIVA PORTAFOGLIO IBKR:
           - Sincronizza il conto e rileva l'eventuale posizione esistente su XAUUSD
        2. ANALISI TECNICA & STORICA XAUUSD (30 giorni e 7 giorni con indicatori reali)
        3. GENERAZIONE STRATEGIA AI SCALPING basata su posizione esistente e condizioni attuali
        4. SALVATAGGIO della strategia attiva in DB come prerequisito per l'avvio del bot
        """
        # --- PASSO 1: Sincronizzazione preventiva Portafoglio IBKR ---
        try:
            if not self.ib_client.is_connected:
                await self.ib_client.connect(timeout=5.0)
        except Exception as e:
            logger.warning("Tentativo di connessione automatica a IBKR Gateway fallito", exc=str(e))

        portfolio = await self.ib_client.get_portfolio()
        acc = portfolio.account

        # Isola e analizza la posizione specifica su XAUUSD
        xauusd_pos = None
        for p in portfolio.positions:
            if p.symbol.upper() in ("XAUUSD", "GOLD"):
                xauusd_pos = p
                break

        if xauusd_pos:
            dir_str = getattr(xauusd_pos.direction, "value", str(xauusd_pos.direction)).upper()
            xauusd_pos_str = (
                f"ATTUALMENTE APERTA: {dir_str} {xauusd_pos.quantity} oz @ ${xauusd_pos.entry_price:.2f} "
                f"(Valore Mercato: ${xauusd_pos.market_value:.2f}, P&L Non Realizzato: ${xauusd_pos.unrealized_pnl:+.2f})"
            )
        else:
            xauusd_pos_str = "NESSUNA POSIZIONE APERTA su XAUUSD al momento (Esposizione 0.0 oz)."

        other_positions = [
            f"{p.symbol} {getattr(p.direction, 'value', str(p.direction)).upper()} {p.quantity} pz (P&L: ${p.unrealized_pnl:+.2f})"
            for p in portfolio.positions
            if p.symbol.upper() not in ("XAUUSD", "GOLD")
        ]
        open_pos_str = f"Posizione XAUUSD: {xauusd_pos_str} | Altri titoli: " + (", ".join(other_positions) if other_positions else "Nessuno")

        # --- PASSO 2: Analisi Dati di Mercato & Trend Storico ---
        mkt: MarketHistoricalContext = await self.market_analyzer.get_xauusd_analysis()

        # --- PASSO 3: Parametri di Trading e Limiti di Rischio ---
        t_params = load_trading_params()
        asset_cfg = t_params.get("assets", {}).get("XAUUSD", {})
        risk_cfg = asset_cfg.get("risk_management", {})

        max_budget = risk_cfg.get("max_budget_per_trade_usd", 5000.0)
        max_size_oz = risk_cfg.get("max_position_size_oz", 2.0)
        stop_loss_pct = risk_cfg.get("stop_loss_pct", 0.005) * 100
        take_profit_pct = risk_cfg.get("take_profit_pct", 0.01) * 100
        allowed_direction = asset_cfg.get("trading", {}).get("direction", "both")

        # --- PASSO 4: Compilazione Robusta del Prompt ---
        prompts = load_ai_prompts()
        ma_prompt = prompts.get("prompts", {}).get("market_analysis", {})
        sys_instruction = ma_prompt.get("system_instruction", "")
        template = ma_prompt.get("analysis_template", "")

        # Mappatura completa di tutti i valori (sia a parentesi singola che doppia)
        context_vars = {
            "symbol": "XAUUSD",
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
            "open_positions": open_pos_str,
            "recent_trades": "Ultimi trade di scalping monitorati sul conto",
            "daily_pnl": f"{portfolio.daily_pnl:+.2f}",
            "trades_today": "0",
            "win_rate_today": "0.0",
            "max_budget": f"{max_budget:,.2f}",
            "max_position_size": f"{max_size_oz}",
            "stop_loss_pct": f"{stop_loss_pct}",
            "take_profit_pct": f"{take_profit_pct}",
            "allowed_direction": allowed_direction,
        }

        # Applica sostituzioni sia per {{var}} che per {var} per massima compatibilità con qualsiasi file di prompt esterno
        filled_prompt = template
        for key, val in context_vars.items():
            filled_prompt = filled_prompt.replace(f"{{{{{key}}}}}", str(val))
            filled_prompt = filled_prompt.replace(f"{{{key}}}", str(val))

        # Aggiunta esplicita della sezione di portafoglio dettagliata per l'AI
        filled_prompt += f"""

## POSIZIONE ESISTENTE SU XAUUSD NEL PORTAFOGLIO IBKR:
- Stato attuale XAUUSD: {xauusd_pos_str}
- Buying Power disponibile: ${acc.buying_power:,.2f}
- Liquidità: ${acc.cash_balance:,.2f}
- Budget massimo consentito per questa operazione: ${max_budget:,.2f}
- NOTA STRATEGICA: Se è già presente una posizione aperta su XAUUSD, valuta se mantenerla (HOLD), incrementarla o chiuderla (CLOSE) in base alla strategia di scalping.
"""

        # --- PASSO 5: Interrogazione Motore AI ---
        ai_result = await self.ai_client.generate_trade_analysis(
            prompt=filled_prompt,
            system_instruction=sys_instruction,
        )

        # --- PASSO 6: Validazione & Normalizzazione della Decisione ---
        action_str = str(ai_result.get("action", "HOLD")).upper()
        confidence = float(ai_result.get("confidence", 0.5))
        reasoning = ai_result.get("reasoning", "Analisi di scalping completata")
        entry_price = float(ai_result.get("entry_price") or mkt.current_price)
        stop_loss = float(ai_result.get("stop_loss") or (round(entry_price * 0.995, 2) if action_str == "BUY" else round(entry_price * 1.005, 2)))
        take_profit = float(ai_result.get("take_profit") or (round(entry_price * 1.01, 2) if action_str == "BUY" else round(entry_price * 0.99, 2)))
        pos_size = float(ai_result.get("position_size_oz") or 1.0)
        pos_size = min(pos_size, max_size_oz)

        strategy_payload = {
            "symbol": "XAUUSD",
            "action": action_str,
            "confidence": confidence,
            "reasoning": reasoning,
            "scalping_setup": ai_result.get("scalping_setup", "Scalping su trend e livelli di supporto/resistenza"),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_size_oz": pos_size,
            "urgency": ai_result.get("urgency", "MEDIUM"),
            "market_sentiment": ai_result.get("market_sentiment", "NEUTRAL"),
            "risk_reward_ratio": float(ai_result.get("risk_reward_ratio", 2.0)),
            "estimated_hold_time_minutes": int(ai_result.get("estimated_hold_time_minutes", 15)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "existing_position": {
                "has_position": bool(xauusd_pos),
                "details": xauusd_pos_str,
                "quantity": float(xauusd_pos.quantity) if xauusd_pos else 0.0,
                "unrealized_pnl": float(xauusd_pos.unrealized_pnl) if xauusd_pos else 0.0,
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
                "budget_per_trade": max_budget,
            },
        }

        # --- PASSO 7: Registrazione nel DB SQLite ---
        db = get_db()
        await db.set_config("active_scalping_strategy", strategy_payload)
        await db.record_ai_decision(
            symbol="XAUUSD",
            action=action_str,
            confidence=confidence,
            reasoning=reasoning,
            market_sentiment=strategy_payload["market_sentiment"],
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_oz=pos_size,
            urgency=strategy_payload["urgency"],
            risk_reward_ratio=strategy_payload["risk_reward_ratio"],
            executed=0,
            rejection_reason="Analisi e definizione strategia completata",
        )

        return strategy_payload

    async def validate_auto_trading_readiness(self) -> dict[str, Any]:
        """
        Verifica se il trading automatico può essere avviato:
        - Controllo presenza di strategia valida recente (< 4 ore)
        - Verifica portafoglio reale e disponibilità di fondi
        - Rispetto del budget massimo stabilito
        """
        db = get_db()
        active_strategy = await db.get_config("active_scalping_strategy")

        if not active_strategy:
            return {
                "can_start": False,
                "reason": "Nessuna strategia definita. Esegui prima l'analisi di mercato per XAUUSD.",
            }

        # Verifica timestamp strategia (massimo 4 ore)
        created_at_str = active_strategy.get("timestamp")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
                delta_minutes = (datetime.now(timezone.utc) - created_at).total_seconds() / 60
                if delta_minutes > 240:
                    return {
                        "can_start": False,
                        "reason": f"La strategia definita è obsoleta ({int(delta_minutes)} min fa). Riavvia l'analisi prima di avviare il bot.",
                    }
            except Exception:
                pass

        # Verifica portafoglio
        portfolio = await self.ib_client.get_portfolio()
        t_params = load_trading_params()
        asset_cfg = t_params.get("assets", {}).get("XAUUSD", {})
        risk_cfg = asset_cfg.get("risk_management", {})
        max_budget = risk_cfg.get("max_budget_per_trade_usd", 5000.0)

        if portfolio.account.buying_power < max_budget and portfolio.account.cash_balance < 1000:
            return {
                "can_start": False,
                "reason": f"Buying power insufficiente (${portfolio.account.buying_power:,.2f}) per il budget richiesto (${max_budget:,.2f}).",
            }

        return {
            "can_start": True,
            "strategy": active_strategy,
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
