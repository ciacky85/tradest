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
    def is_connected(self) -> bool:
        """Indica se il client è attualmente connesso a IBKR Gateway/TWS."""
        if self._ib is not None:
            try:
                return bool(self._ib.isConnected())
            except Exception:
                pass
        return self._connected

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Tenta la connessione a IB Gateway / TWS.
        Se ib_insync è disponibile, usa la classe IB asincrona.
        Altrimenti verifica la raggiungibilità del socket TCP.
        """
        async with self._lock:
            # Prova prima con ib_insync se installato
            try:
                from ib_insync import IB
                if self._ib is None:
                    self._ib = IB()
                
                if self._ib.isConnected():
                    self._connected = True
                    return True

                logger.info(
                    "Connessione a IBKR Gateway in corso...",
                    host=self.host,
                    port=self.port,
                    client_id=self.client_id,
                    mode=self.trading_mode,
                )
                
                # Esegui connectAsync con timeout
                await asyncio.wait_for(
                    self._ib.connectAsync(
                        host=self.host,
                        port=self.port,
                        clientId=self.client_id,
                        timeout=timeout,
                    ),
                    timeout=timeout + 2.0,
                )
                self._connected = self._ib.isConnected()
                if self._connected:
                    logger.info("Connesso con successo a IBKR Gateway/TWS")
                    accounts = self._ib.managedAccounts()
                    if accounts and not self.account_id:
                        self.account_id = accounts[0]
                    return True
            except ImportError:
                logger.warning("ib_insync non installato, fallback su verifica socket TCP")
            except Exception as e:
                logger.warning("Connessione ib_insync non riuscita, verifica socket fallback", error=str(e))

            # Fallback di verifica connettività TCP diretta
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
                self._connected = True
                logger.info("Socket IBKR Gateway raggiungibile", host=self.host, port=self.port)
                return True
            except Exception as exc:
                self._connected = False
                logger.error("Impossibile raggiungere IBKR Gateway", host=self.host, port=self.port, error=str(exc))
                return False

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

    async def get_portfolio(self) -> Portfolio:
        """
        Recupera i dati del portafoglio (liquidità, cash, margine, P&L, posizioni) da IBKR.
        Se connesso a IBKR, interroga l'accountSummary o portfolio().
        Se il gateway non è attivo o siamo in modalità simulazione senza broker attivo,
        fornisce il riepilogo coerente.
        """
        if self._ib is not None and self._ib.isConnected():
            try:
                # Estrae i valori dall'accountSummary di ib_insync
                account_values = await self._ib.accountSummaryAsync(self.account_id)
                summary_map = {val.tag: float(val.value) for val in account_values if val.currency in ("USD", "EUR", "") and val.value.replace(".", "", 1).replace("-", "", 1).isdigit()}
                
                net_liquidation = summary_map.get("NetLiquidation", 100000.0)
                total_cash = summary_map.get("TotalCashValue", net_liquidation)
                buying_power = summary_map.get("BuyingPower", net_liquidation * 4)
                unrealized_pnl = summary_map.get("UnrealizedPnL", 0.0)
                realized_pnl = summary_map.get("RealizedPnL", 0.0)

                # Posizioni correnti
                ib_positions = self._ib.positions(self.account_id)
                positions_list: list[Position] = []
                for p in ib_positions:
                    pos_obj = Position(
                        symbol=p.contract.symbol,
                        quantity=float(p.position),
                        average_cost=float(p.avgCost),
                        current_price=float(p.avgCost), # aggiornato poi da market data
                        market_value=float(p.position * p.avgCost),
                        unrealized_pnl=0.0,
                    )
                    positions_list.append(pos_obj)

                return Portfolio(
                    account_id=self.account_id or (self._ib.managedAccounts()[0] if self._ib.managedAccounts() else "SIM_IBKR"),
                    net_liquidation=net_liquidation,
                    total_cash=total_cash,
                    buying_power=buying_power,
                    unrealized_pnl=unrealized_pnl,
                    realized_pnl=realized_pnl,
                    positions=positions_list,
                    updated_at=datetime.utcnow(),
                )
            except Exception as e:
                logger.error("Errore recupero portfolio da ib_insync", error=str(e))

        # Fallback coerente per modalità simulazione / broker non ancora connesso
        sim_account = f"{'DU' if self.trading_mode == 'paper' else 'U'}_SIMULATED_{self.username or 'USER'}"
        return Portfolio(
            account_id=self.account_id or sim_account,
            net_liquidation=100000.0,
            total_cash=100000.0,
            buying_power=400000.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            positions=[],
            updated_at=datetime.utcnow(),
        )

    async def get_trades(self) -> list[TradeRecord]:
        """Recupera i trade e le esecuzioni recenti."""
        if self._ib is not None and self._ib.isConnected():
            try:
                executions = self._ib.executions()
                trades: list[TradeRecord] = []
                for fill in executions:
                    trades.append(
                        TradeRecord(
                            id=str(fill.execId),
                            order_id=str(fill.orderId),
                            symbol=fill.contract.symbol,
                            action=fill.side,
                            quantity=float(fill.shares),
                            price=float(fill.price),
                            commission=0.0,
                            realized_pnl=0.0,
                            executed_at=datetime.utcnow(),
                        )
                    )
                return trades
            except Exception as e:
                logger.error("Errore recupero trades da IBKR", error=str(e))
        return []


# Istanza singleton
_ibkr_client: Optional[IBKRClient] = None


def get_ibkr_client() -> IBKRClient:
    """Restituisce l'istanza singleton del client IBKR."""
    global _ibkr_client
    if _ibkr_client is None:
        _ibkr_client = IBKRClient()
    return _ibkr_client
