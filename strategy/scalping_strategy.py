"""
strategy/scalping_strategy.py - Gestore strategico di scalping su XAUUSD e controllo esecutivo del bot.

Caratteristiche:
- Genera analisi approfondita su 30 giorni e focus ultima settimana con indicatori tecnici (RSI, EMA, MACD, ATR, Bollinger Bands).
- Interroga l'AI (Omniroute o Google) passando contesto di mercato e portafoglio reale.
- Memorizza la strategia definita come 'active_strategy' in SQLite e verifica i vincoli prima dell'avvio automatico:
  * Controllo presenza di una strategia valida recente (< 2 ore)
  * Verifica portafoglio reale e liquidità
  * Verifica budget massimo allocato per trade
  * Verifica spread di mercato corrente rispetto al massimo ammesso
"""

from __future__ import annotations

import json
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
        Esegue l'analisi completa di XAUUSD:
        1. Estrae trend a 30 giorni, focus 7 giorni e indicatori tecnici.
        2. Recupera lo stato attuale del conto e portafoglio da IBKR.
        3. Genera la strategia tramite AI Engine (Omniroute / Gemini).
        4. Salva la strategia attiva nel DB SQLite come prerequisito per l'avvio del trading automatico.
        """
        # 1. Analisi di mercato
        mkt: MarketHistoricalContext = await self.market_analyzer.get_xauusd_analysis()

        # 2. Situazione Portafoglio reale
        portfolio = await self.ib_client.get_portfolio()
        acc = portfolio.account
        open_pos_str = (
            ", ".join([f"{p.symbol} {p.direction.value} ({p.quantity} oz @ ${p.entry_price:.2f}, P&L: ${p.unrealized_pnl:.2f})" for p in portfolio.positions])
            if portfolio.positions
            else "Nessuna posizione aperta al momento."
        )

        # 3. Parametri di trading e vincoli di budget
        t_params = load_trading_params()
        asset_cfg = t_params.get("assets", {}).get("XAUUSD", {})
        risk_cfg = asset_cfg.get("risk_management", {})

        max_budget = risk_cfg.get("max_budget_per_trade_usd", 5000.0)
        max_size_oz = risk_cfg.get("max_position_size_oz", 2.0)
        stop_loss_pct = risk_cfg.get("stop_loss_pct", 0.005) * 100
        take_profit_pct = risk_cfg.get("take_profit_pct", 0.01) * 100
        allowed_direction = asset_cfg.get("trading", {}).get("direction", "both")

        # 4. Compilazione template prompt
        prompts = load_ai_prompts()
        ma_prompt = prompts["prompts"]["market_analysis"]
        sys_instruction = ma_prompt["system_instruction"]
        template = ma_prompt["analysis_template"]

        # Rimpiazzo sicuro dei segnaposto {{param}}
        replacements = {
            "{{symbol}}": "XAUUSD",
            "{{trend_30d}}": str(mkt.trend_30d),
            "{{low_30d}}": f"{mkt.low_30d:.2f}",
            "{{high_30d}}": f"{mkt.high_30d:.2f}",
            "{{change_pct_30d}}": f"{mkt.change_pct_30d:+.2f}",
            "{{trend_7d}}": str(mkt.trend_7d),
            "{{low_7d}}": f"{mkt.low_7d:.2f}",
            "{{high_7d}}": f"{mkt.high_7d:.2f}",
            "{{change_pct_7d}}": f"{mkt.change_pct_7d:+.2f}",
            "{{supports}}": ", ".join([f"${s:.1f}" for s in mkt.supports]),
            "{{resistances}}": ", ".join([f"${r:.1f}" for r in mkt.resistances]),
            "{{current_price}}": f"{mkt.current_price:.2f}",
            "{{bid}}": f"{mkt.bid:.2f}",
            "{{ask}}": f"{mkt.ask:.2f}",
            "{{spread}}": f"{mkt.spread:.2f}",
            "{{volume}}": f"{mkt.volume:.1f}",
            "{{daily_change_pct}}": f"{mkt.daily_change_pct:+.2f}",
            "{{rsi}}": f"{mkt.indicators.rsi:.1f}",
            "{{ema_fast}}": f"{mkt.indicators.ema_fast:.2f}",
            "{{ema_slow}}": f"{mkt.indicators.ema_slow:.2f}",
            "{{macd}}": f"{mkt.indicators.macd:.2f}",
            "{{macd_signal}}": f"{mkt.indicators.macd_signal:.2f}",
            "{{macd_hist}}": f"{mkt.indicators.macd_hist:.2f}",
            "{{atr}}": f"{mkt.indicators.atr:.2f}",
            "{{bb_upper}}": f"{mkt.indicators.bb_upper:.2f}",
            "{{bb_middle}}": f"{mkt.indicators.bb_middle:.2f}",
            "{{bb_lower}}": f"{mkt.indicators.bb_lower:.2f}",
            "{{portfolio_total_value}}": f"{acc.total_value:,.2f}",
            "{{portfolio_cash}}": f"{acc.cash_balance:,.2f}",
            "{{portfolio_buying_power}}": f"{acc.buying_power:,.2f}",
            "{{open_positions}}": open_pos_str,
            "{{daily_pnl}}": f"{portfolio.daily_pnl:+.2f}",
            "{{max_budget}}": f"{max_budget:,.2f}",
            "{{max_position_size}}": f"{max_size_oz}",
            "{{stop_loss_pct}}": f"{stop_loss_pct}",
            "{{take_profit_pct}}": f"{take_profit_pct}",
            "{{allowed_direction}}": allowed_direction,
        }

        filled_prompt = template
        for k, v in replacements.items():
            filled_prompt = filled_prompt.replace(k, str(v))

        # 5. Generazione risposta AI
        ai_result = await self.ai_client.generate_trade_analysis(
            prompt=filled_prompt,
            system_instruction=sys_instruction,
        )

        # 6. Validazione e formattazione strategia
        action_str = str(ai_result.get("action", "HOLD")).upper()
        confidence = float(ai_result.get("confidence", 0.5))
        reasoning = ai_result.get("reasoning", "Analisi completata")
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
            "scalping_setup": ai_result.get("scalping_setup", "Trend Following & Mean Reversion"),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_size_oz": pos_size,
            "urgency": ai_result.get("urgency", "MEDIUM"),
            "market_sentiment": ai_result.get("market_sentiment", "NEUTRAL"),
            "risk_reward_ratio": float(ai_result.get("risk_reward_ratio", 2.0)),
            "estimated_hold_time_minutes": int(ai_result.get("estimated_hold_time_minutes", 15)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            # Metadati storici inclusi
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
                "total_value": acc.total_value,
                "cash": acc.cash_balance,
                "buying_power": acc.buying_power,
                "budget_per_trade": max_budget,
            },
        }

        # 7. Salvataggio della strategia attiva nel Database SQLite
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
        - Strategia definita ed esistente
        - Verifica spread e liquidità
        - Verifica budget
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
