
from loguru import logger

from algotrade.common.data_models import CurrencyPair, Trade
from algotrade.common.enums import BrokerTopic, Side
from algotrade.config import get_config
from algotrade.orders_manager import OrdersManager
from algotrade.pubsub import PubSub

config = get_config()


class PnLMonitor:
    """pair-wise PnL monitor with alarm"""

    def __init__(self, cp: PubSub , ord_manager: OrdersManager):
        self._cp = cp
        self._ord_manager = ord_manager
        self._pnl: dict[CurrencyPair, tuple[float, float]] = {}
        self._panic_threshodls: dict[CurrencyPair, float] = {}

    async def on_trade_in(self, trade: Trade):
        ord = self._ord_manager.get_order(trade.uuid)
        size, amt = self._pnl.get(ord.pair, (0, 0))
        size += trade.size if ord.side == Side.BUY else -trade.size
        amt += -trade.amount if ord.side == Side.BUY else trade.amount
        self._pnl[ord.pair] = (size, amt)
        pth = self._panic_threshodls.get(ord.pair, 0)
        if amt < pth:
            msg = f"pnl loss threshold hit for pair: {ord.pair}"
            # self._cp._emitter.emit(Topic.PANIC.name, msg)
            logger.info(msg)
            order = self._ord_manager.get_order(trade.uuid)
            pair = order.pair
            mkt = order.market
            self._cp.publish((BrokerTopic.PANIC, pair, mkt, ), msg)
