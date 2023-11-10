from uuid import UUID

from loguru import logger

from algotrade.common.data_models import (CurrencyPair, Order,
                                          OrderStatusUpdate,
                                          OrderStatusUpdateType, Trade)
from algotrade.common.enums import BrokerTopic, Side
from algotrade.pubsub import PubSub


class OrderOverFlowError(Exception):
    pass


class TradeOnDeadOrderError(Exception):
    """
    It should never make sense. TODO
    """
    pass

class UnknownOrderError(Exception):
    pass


class OrdersManager:
    def __init__(self, ps: PubSub):
        self._ps = ps
        self._orders: dict[UUID, Order] = {}
        self._pnl: dict[CurrencyPair, tuple[float, float]] = {}

    def on_orders_out(self, orders: list[Order]):
        """
        add the orders. There is no assumption that the orders successfully reached any market
        """
        for order in orders:
            self._orders[order.uuid] = order

    def on_trade_in(self, trade: Trade):
        order: Order = self._orders[trade.uuid]
        if not order.live:
            raise TradeOnDeadOrderError
        if trade.size + order.filled_size > order.size:
            raise OrderOverFlowError
        order.filled_amount += trade.amount
        order.filled_size += trade.size
        order.cum_fee += trade.fee
        self._update_pnl(trade, order)
        self._on_trade_log(trade, order)

    async def on_order_update(self, update: OrderStatusUpdate):
        # TODO put in a dicts
        # TODO move panic to a new object reject handler
        order = update.order
        if order:
            self._orders[order.uuid] = order
        elif update.uuid in self._orders:
            order = self._orders[update.uuid]
        else:
            raise UnknownOrderError
        match update.update_type:
            case OrderStatusUpdateType.ACCEPTED:
                order.live = True
                logger.info(f"{str(update.uuid)}: ACCEPTED")  # type: ignore
            case OrderStatusUpdateType.TRADE:
                logger.info(f"{str(update.uuid)}: TRADE, fill: {order.rel_fill()*100}%, pair: {order.pair}, market: {order.market.name}")  # type: ignore
            case OrderStatusUpdateType.REJECTED:
                # TODO check reason before panic
                await self._ps.publish((BrokerTopic.PANIC, order.pair, order.market), "order rejected")
                order.live = False
                logger.critical("PANIC")
                logger.info(f"{str(update.uuid)}: REJECTED, reason: {update.reject_reason}, pair: {order.pair}, market: {order.market.name}")  # type: ignore
            case OrderStatusUpdateType.CANCELED:
                order.live = False
                logger.info(f"{str(update.uuid)}: CANCELED, filled: {order.rel_fill()*100}%, pair: {order.pair}, market: {order.market.name}")  # type: ignore
            case OrderStatusUpdateType.DONE:
                order.live = False
                logger.info(f"{str(update.uuid)}: DONE, pair: {order.pair}, market: {order.market.name}")  # type: ignore

    def get_order(self, uuid: UUID):
        return self._orders[uuid]

    def is_live(self, uuid: UUID):
        return self._orders[uuid].live

    def _on_trade_log(self, trade, order):
        percentage = order.filled_size / order.size * 100
        logger.debug(f"{str(trade.uuid)}, size: {trade.size}, amount: {trade.amount}, fee: {trade.fee}")  # type: ignore
        logger.debug(f"{str(trade.uuid)}, filled size: {order.filled_size}, filled amount: {order.filled_amount}, {percentage}")  # type: ignore

    def _update_pnl(self, trade: Trade, order: Order):
        size, amt = self._pnl.get(order.pair, (0.0, 0.0))
        size += trade.size if order.side == Side.BUY else -trade.size
        amt -= trade.amount if order.side == Side.BUY else -trade.amount
        self._pnl[order.pair] = (size, amt)
        logger.debug(f"pair: {order.pair}, size: {size}, amount:{amt}")  # type: ignore