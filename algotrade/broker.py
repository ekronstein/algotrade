from uuid import UUID

from algotrade.common.data_models import (BookUpdate, CurrencyPair, Order,
                                          OrderStatusUpdate, Trade, Quote)
from algotrade.common.enums import BrokerTopic, MarketName
from algotrade.order_book.order_book import L2OrderBook
from algotrade.orders_manager import OrdersManager
from algotrade.pnl_monitor import PnLMonitor
from algotrade.pubsub import PubSub


class Broker:
    """
    A Broker is meant to be the only object needed for an Algorithm object to perform its functions.
    It may be queried about the state of: prices, orders, positions and P&L. It is also responsible to pass events
    relevant to any Algorithm object, such that an Algorithm is only concerned with `BrokerTopic` events.

    Event topics published by this objects:
        (BrokerTopic.CANCEL_ORDERS_OUT, order.market)
        (BrokerTopic.ORDERS_OUT, market)
        BrokerTopic.BOOK_UPDATE
        BrokerTopic.QUOTE_UPDATE
        BrokerTopic.ORDER_STATUS_UPDATE
    """
    def __init__(self, ps: PubSub):
        self._ps = ps
        self._orders_manager = OrdersManager(ps)
        self._pnl_monitor = PnLMonitor(ps, self._orders_manager)
        self._order_book: dict[tuple[CurrencyPair, MarketName], L2OrderBook] = {}

    async def on_book_update(self, update: BookUpdate):
        book = self._order_book.setdefault((update.pair, update.market), L2OrderBook())
        book.update(update.bids, update.asks)
        await self._ps.publish(BrokerTopic.BOOK_UPDATE, update)

    async def on_quote_update(self, update: Quote):
        # TODO additional ops?
        await self._ps.publish(BrokerTopic.QUOTE_UPDATE, update)
    
    async def on_order_update(self, update: OrderStatusUpdate):
        await self._orders_manager.on_order_update(update)
        await self._ps.publish(BrokerTopic.ORDER_STATUS_UPDATE, update)

    async def on_trade(self, trade: Trade):
        self._orders_manager.on_trade_in(trade)

    def is_order_live(self, uuid):
        return self._orders_manager.is_live(uuid)

    def get_order(self, uuid: UUID):
        return self._orders_manager.get_order(uuid)

    async def publish_orders(self, orders: list[Order]):
        """
        All orders assumed to be of the same market
        """
        self._orders_manager.on_orders_out(orders)
        await self._ps.publish((BrokerTopic.ORDERS_OUT, orders[0].market), orders)
    
    async def cancel_orders(self, uuids: list[UUID]):
        """
        Assumes all uuids belong to orders of the same market
        """
        order = self._orders_manager.get_order(uuids[0])
        await self._ps.publish((BrokerTopic.CANCEL_ORDERS_OUT, order.market), uuids)


