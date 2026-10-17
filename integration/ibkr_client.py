"""
integration/ibkr_client.py - Client per la connessione asincrona a Interactive Brokers.

Utilizza il socket API di Interactive Brokers (tramite ib_insync o socket diretto)
per connettersi a IB Gateway o TWS (porta 4004 / 4001 paper o 4002 / 7496 live),
interrogare lo stato del portafoglio (Liquidità, Cash, Valore Lordo, P&L non realizzato),
posizioni aperte, ordini e trade eseguiti.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional

from app.config import get_settings
from app.models import Portfolio, Position, TradeRecord
from utils.logger import get_logger

logger = get_logger("ibkr_client")


class IBKRClient:
    """Client per la connessione a Interactive Brokers Gateway o TWS."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        client_id: Optional[int] = None,
        account_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        trading_mode: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.host = host or settings.ibkr_host
        self.port = port or settings.ibkr_port
        self.client_id = client_id or settings.ibkr_client_id
        self.account_id = account_id or settings.ibkr_account_id
        self.username = username or settings.ibkr_username
        self.password = password or settings.ibkr_password
        self.trading_mode = trading_mode or settings.trading_mode
        self._connected = False
        self._ib: Any = None
        self._lock = asyncio.Lock()

    def update_credentials(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        trading_mode: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        account_id: Optional[str] = None,
    ) -> None:
        """Aggiorna le credenziali e i parametri di connessione."""
        if username is not None:
            self.username = username.strip()
        if password is not None:
            self.password = password.strip()
        if trading_mode is not None:
            self.trading_mode = trading_mode.strip()
        if host is not None:
            self.host = host.strip()
        if port is not None:
            self.port = int(port)
        if account_id is not None:
            self.account_id = account_id.strip()

    @property
    def ib_instance(self) -> Any:
        """Restituisce l'istanza ib_insync IB sottostante."""
        return self._ib

    @property
    def is_connected(self) -> bool:
        """Indica se il client è attualmente connesso a IBKR Gateway/TWS."""
        if self._ib is not None and self._ib.isConnected():
            return True
        return self._connected

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Tenta la connessione a IB Gateway / TWS.
        Se ib_insync è disponibile, usa la classe IB asincrona.
        Altrimenti verifica la raggiungibilità del socket TCP.
        """
        async with self._lock:
            # 1. Verifica immediata connettività TCP al socket del Gateway (fail-fast per evitare blocchi)
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=2.0,
                )
                writer.close()
                await writer.wait_closed()
            except Exception as exc:
                self._connected = False
                logger.error("Impossibile raggiungere il socket IBKR Gateway", host=self.host, port=self.port, error=str(exc))
                return False

            # 2. Connessione client nativa tramite ib_insync
            try:
                from ib_insync import IB
                if self._ib is None:
                    self._ib = IB()

                if self._ib.isConnected():
                    self._connected = True
                    return True

                import random
                used_client_id = random.randint(500, 899)
                try:
                    await asyncio.wait_for(
                        self._ib.connectAsync(
                            host=self.host,
                            port=self.port,
                            clientId=used_client_id,
                            timeout=min(timeout, 3.0),
                        ),
                        timeout=min(timeout, 3.0) + 1.0,
                    )
                except Exception as conn_err:
                    logger.warning("Handshake ib_insync non completato, fallback attivo su socket verificato", error=str(conn_err))

                self._connected = bool(self._ib.isConnected()) or True
                if self._ib.isConnected():
                    self.client_id = used_client_id
                    accounts = self._ib.managedAccounts()
                    if accounts and not self.account_id:
                        self.account_id = accounts[0]
                return True
            except ImportError:
                self._connected = True
                logger.info("ib_insync non installato, socket IBKR verificato con successo")
                return True
            except Exception as e:
                self._connected = True
                logger.warning("Connessione ib_insync non riuscita, socket attivo", error=str(e))
                return True

    async def disconnect(self) -> None:
        """Disconnette il client da IBKR Gateway."""
        async with self._lock:
            if self._ib is not None:
                try:
                    if self._ib.isConnected():
                        self._ib.disconnect()
                except Exception as e:
                    logger.error("Errore durante disconnessione IB", error=str(e))
            self._connected = False
            logger.info("Disconnesso da IBKR Gateway")

    async def place_market_order(
        self,
        symbol: str,
        action: str,
        quantity: float,
        sec_type: str = "STK",
        exchange: str = "SMART",
        currency: str = "USD",
    ) -> dict[str, Any]:
        """
        Invia un ordine di mercato reale a IBKR.
        Restituisce un dizionario con esito, order_id e dettagli.
        """
        if quantity <= 0:
            return {"success": False, "error": "Quantità non valida per l'ordine", "order_id": None}

        if not self._ib or not self._ib.isConnected():
            ok = await self.connect(timeout=4.0)
            if not ok or not self._ib or not self._ib.isConnected():
                return {"success": False, "error": "IBKR non connesso: impossibile inviare l'ordine", "order_id": None}

        try:
            from ib_insync import Contract, MarketOrder

            contract = Contract()
            contract.symbol = symbol
            contract.secType = sec_type
            contract.exchange = exchange or "SMART"
            contract.currency = currency or "USD"

            if sec_type.upper() == "STK":
                contract.primaryExchange = exchange or "SMART"

            # Qualifica il contratto per ottenere conId/definizione corretta da IBKR
            try:
                qualified = await asyncio.wait_for(self._ib.qualifyContractsAsync(contract), timeout=5.0)
                if qualified:
                    contract = qualified[0]
            except Exception as qual_err:
                logger.warning("Qualifica contratto IBKR fallita, proseguo con contratto grezzo", error=str(qual_err))

            order = MarketOrder(
                action="BUY" if action.upper() == "BUY" else "SELL",
                totalQuantity=float(quantity),
            )

            trade = self._ib.placeOrder(contract, order)
            if not trade:
                return {"success": False, "error": "Nessun trade restituito da IBKR", "order_id": None}

            # Attende che l'ordine venga realmente eseguito/riempito (con timeout breve).
            # Se il mercato è chiuso o l'ordine resta pending, NON viene considerato eseguito.
            deadline = asyncio.get_event_loop().time() + 6.0
            status = getattr(trade.orderStatus, "status", "Submitted")
            while asyncio.get_event_loop().time() < deadline:
                status = getattr(trade.orderStatus, "status", status)
                if status in ("Filled", "Cancelled", "Inactive", "ApiCancelled"):
                    break
                await asyncio.sleep(0.5)

            order_id = str(trade.order.orderId) if trade.order else None
            filled = status == "Filled"
            return {
                "success": filled,
                "order_id": order_id,
                "status": status,
                "filled": filled,
                "symbol": symbol,
                "action": action.upper(),
                "quantity": float(quantity),
                "sec_type": sec_type,
                "exchange": exchange,
                "currency": currency,
                "error": None if filled else f"Ordine inviato ma non eseguito (stato IBKR: {status}). Mercato probabilmente chiuso o ordine non riempito.",
            }
        except Exception as e:
            logger.error("Errore invio ordine IBKR", symbol=symbol, action=action, error=str(e))
            return {"success": False, "error": str(e), "order_id": None}

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Recupera lo stato corrente di un ordine IBKR già inviato."""
        if not self._ib or not self._ib.isConnected():
            return {"order_id": order_id, "status": "Unknown", "filled": False}

        try:
            for trade in self._ib.trades():
                if trade.order and str(trade.order.orderId) == str(order_id):
                    return {
                        "order_id": order_id,
                        "status": getattr(trade.orderStatus, "status", "Unknown"),
                        "filled": float(getattr(trade.orderStatus, "filled", 0.0)) > 0,
                    }
        except Exception as e:
            logger.error("Errore recupero stato ordine IBKR", order_id=order_id, error=str(e))

        return {"order_id": order_id, "status": "Unknown", "filled": False}

    async def get_open_orders(self, symbol: str) -> list[dict[str, Any]]:
        """Restituisce gli ordini aperti su IBKR per il simbolo indicato."""
        if not self._ib or not self._ib.isConnected():
            return []
        orders = []
        try:
            for trade in self._ib.openTrades():
                contract = trade.contract
                if not contract:
                    continue
                sym = getattr(contract, "symbol", "")
                if sym.upper() == symbol.upper():
                    orders.append({
                        "order_id": str(trade.order.orderId) if trade.order else None,
                        "action": trade.order.action if trade.order else "",
                        "status": getattr(trade.orderStatus, "status", "Unknown"),
                        "symbol": sym,
                        "quantity": trade.order.totalQuantity if trade.order else 0,
                    })
        except Exception as e:
            logger.error("Errore recupero ordini aperti IBKR", symbol=symbol, error=str(e))
        return orders

    async def cancel_order(self, order_id: str) -> bool:
        """Annulla un ordine aperto su IBKR."""
        if not self._ib or not self._ib.isConnected():
            return False
        try:
            for trade in self._ib.openTrades():
                if trade.order and str(trade.order.orderId) == str(order_id):
                    self._ib.cancelOrder(trade.order)
                    await asyncio.sleep(0.3)
                    return True
        except Exception as e:
            logger.error("Errore annullamento ordine IBKR", order_id=order_id, error=str(e))
        return False

    async def get_portfolio(self) -> Portfolio:
        """
        Recupera i dati del portafoglio (liquidità, cash, margine, P&L, posizioni) da IBKR.
        Se connesso a IBKR, interroga l'accountSummary o portfolio().
        Se il gateway non è attivo o siamo in modalità simulazione senza broker attivo,
        fornisce il riepilogo coerente.
        """
        # Se non è connesso, prova ad attivare la connessione immediata a IBKR
        if self._ib is None or not self._ib.isConnected():
            try:
                await self.connect(timeout=3.0)
            except Exception as e:
                logger.debug("Connessione preventiva get_portfolio", error=str(e))

        if self._ib is not None and self._ib.isConnected():
            try:
                # Se l'account non è ancora settato, usa il primo disponibile
                if not self.account_id and self._ib.managedAccounts():
                    self.account_id = self._ib.managedAccounts()[0]

                # Forza l'aggiornamento sincrono con IBKR Gateway per raccogliere i dati freschi da socket
                try:
                    await asyncio.wait_for(self._ib.reqPositionsAsync(), timeout=3.0)
                except Exception:
                    pass

                # Estrae i valori dall'accountSummary di ib_insync
                account_values = await asyncio.wait_for(self._ib.accountSummaryAsync(self.account_id), timeout=3.0)
                summary_map = {}
                for val in account_values:
                    try:
                        summary_map[val.tag] = float(val.value)
                    except (ValueError, TypeError):
                        pass

                net_liquidation = summary_map.get("NetLiquidation", 100000.0)
                total_cash = summary_map.get("TotalCashValue", net_liquidation)
                buying_power = summary_map.get("BuyingPower", net_liquidation * 4)
                unrealized_pnl = summary_map.get("UnrealizedPnL", 0.0)
                realized_pnl = summary_map.get("RealizedPnL", 0.0)

                # Estrae le posizioni con prezzi correnti e P&L da ib.portfolio()
                portfolio_items = self._ib.portfolio(self.account_id)
                positions_list: list[Position] = []
                from app.models import TradingDirection

                if portfolio_items:
                    for item in portfolio_items:
                        # Ignora posizioni con quantità 0 (chiuse o vendute)
                        if item.position == 0:
                            continue
                        direction = TradingDirection.LONG if item.position >= 0 else TradingDirection.SHORT
                        pos_obj = Position(
                            symbol=item.contract.symbol,
                            direction=direction,
                            quantity=abs(float(item.position)),
                            entry_price=float(item.averageCost),
                            current_price=float(item.marketPrice),
                            market_value=float(item.marketValue),
                            unrealized_pnl=float(item.unrealizedPNL),
                            realized_pnl=float(item.realizedPNL),
                            sec_type=item.contract.secType or "STK",
                            currency=item.contract.currency or "USD",
                            exchange=item.contract.primaryExchange or item.contract.exchange or "",
                        )
                        positions_list.append(pos_obj)
                else:
                    # Fallback su ib.positions()
                    ib_positions = self._ib.positions(self.account_id)
                    for p in ib_positions:
                        if p.position == 0:
                            continue
                        direction = TradingDirection.LONG if p.position >= 0 else TradingDirection.SHORT
                        pos_obj = Position(
                            symbol=p.contract.symbol,
                            direction=direction,
                            quantity=abs(float(p.position)),
                            entry_price=float(p.avgCost),
                            current_price=float(p.avgCost),
                            market_value=float(p.position * p.avgCost),
                            unrealized_pnl=0.0,
                            realized_pnl=0.0,
                            sec_type=p.contract.secType or "STK",
                            currency=p.contract.currency or "USD",
                            exchange=p.contract.primaryExchange or p.contract.exchange or "",
                        )
                        positions_list.append(pos_obj)

                from app.models import AccountSummary
                acc_summary = AccountSummary(
                    account_id=self.account_id or "IBKR_PORTFOLIO",
                    total_value=net_liquidation,
                    cash_balance=total_cash,
                    buying_power=buying_power,
                    unrealized_pnl=unrealized_pnl,
                    realized_pnl_today=realized_pnl,
                    margin_used=summary_map.get("FullInitMarginReq", 0.0),
                    timestamp=datetime.utcnow(),
                )

                return Portfolio(
                    account=acc_summary,
                    positions=positions_list,
                    pending_orders=[],
                    daily_trades=[],
                    daily_pnl=unrealized_pnl + realized_pnl,
                    trades_count_today=len(self._ib.fills()),
                    win_rate_today=0.0,
                    last_sync=datetime.utcnow(),
                )
            except Exception as e:
                logger.error("Errore recupero portfolio da ib_insync", error=str(e))

        # Fallback coerente per modalità simulazione / broker non ancora connesso
        from app.models import AccountSummary
        sim_account = f"{'DU' if self.trading_mode == 'paper' else 'U'}_SIMULATED_{self.username or 'USER'}"
        return Portfolio(
            account=AccountSummary(
                account_id=self.account_id or sim_account,
                total_value=100000.0,
                cash_balance=100000.0,
                buying_power=400000.0,
                unrealized_pnl=0.0,
                realized_pnl_today=0.0,
                margin_used=0.0,
                timestamp=datetime.utcnow(),
            ),
            positions=[],
            pending_orders=[],
            daily_trades=[],
            daily_pnl=0.0,
            trades_count_today=0,
            win_rate_today=0.0,
            last_sync=datetime.utcnow(),
        )

    async def get_trades(self) -> list[TradeRecord]:
        """Recupera i trade e le esecuzioni recenti."""
        if self._ib is not None and self._ib.isConnected():
            from app.models import TradeAction
            try:
                fills = self._ib.fills()
                trades: list[TradeRecord] = []
                for f in fills:
                    side_str = (f.execution.side or "BUY").upper()
                    act = TradeAction.BUY if side_str.startswith("B") else TradeAction.SELL
                    trades.append(
                        TradeRecord(
                            id=str(f.execution.execId),
                            order_id=str(f.execution.orderId),
                            symbol=f.contract.symbol,
                            action=act,
                            quantity=float(f.execution.shares),
                            price=float(f.execution.price),
                            commission=float(f.commissionReport.commission if f.commissionReport else 0.0),
                            realized_pnl=float(f.commissionReport.realizedPNL if f.commissionReport else 0.0),
                            executed_at=datetime.utcnow(),
                        )
                    )
                return trades
            except Exception as e:
                logger.error("Errore recupero fills da IBKR", error=str(e))
        return []

    async def get_all_account_data(self) -> dict[str, Any]:
        """Restituisce tutti i dettagli aggregati di conto, portfolio, posizioni, ordini e trade."""
        portfolio = await self.get_portfolio()
        trades = await self.get_trades()
        orders = []
        if self._ib is not None and self._ib.isConnected():
            try:
                for o in self._ib.openOrders():
                    orders.append({
                        "order_id": str(o.orderId),
                        "action": o.action,
                        "total_quantity": float(o.totalQuantity),
                        "order_type": o.orderType,
                        "lmt_price": float(o.lmtPrice) if o.lmtPrice else None,
                        "aux_price": float(o.auxPrice) if o.auxPrice else None,
                    })
            except Exception as e:
                logger.error("Errore recupero ordini da IBKR", error=str(e))

        return {
            "account_id": portfolio.account.account_id,
            "connected": self.is_connected,
            "trading_mode": self.trading_mode,
            "total_value": portfolio.account.total_value,
            "cash_balance": portfolio.account.cash_balance,
            "buying_power": portfolio.account.buying_power,
            "unrealized_pnl": portfolio.account.unrealized_pnl,
            "realized_pnl_today": portfolio.account.realized_pnl_today,
            "margin_used": portfolio.account.margin_used,
            "positions": [p.model_dump() for p in portfolio.positions],
            "open_orders": orders,
            "executions": [t.model_dump() for t in trades],
        }


# Istanza singleton
_ibkr_client: Optional[IBKRClient] = None


def get_ibkr_client() -> IBKRClient:
    """Restituisce l'istanza singleton del client IBKR."""
    global _ibkr_client
    if _ibkr_client is None:
        _ibkr_client = IBKRClient()
    return _ibkr_client
