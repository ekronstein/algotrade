from dataclasses import dataclass
import json
import asyncio
import random
from algotrade.algotrade import AlgoTrade
from algotrade.algo.bbba.price_server import PriceServer
from algotrade.common.enums import MarketName, Side
from algotrade.common.data_models import CurrencyPair, BookUpdate, OrderStatusUpdate, OrderStatusUpdateType, Quote
from algotrade.order_book.order_book import L2OrderBook, diff


@dataclass
class PriceSize:
    price: float
    size: float

SIGN = {Side.BUY: 1, Side.SELL: -1}
EXTREME = {Side.BUY: max, Side.SELL: min}


class BBBA:
    """
    Implements Algorithm protocol

    config parameters:
        ORDER_AMOUNT - positive number, representing the amount of a new order, quote leg units
        REFRESH_AMOUNT - positive number, representing the amount left to fill an order, below which we replace it by a new one, with amount ORDER_AMOUNT, quote leg units
        IGNORE_SIZE - non-negative number, representing the size from the top of the book to consider irrelevant. i.e. the best order in a LOB is considered to be the order left after removing IGNORE_SIZE from the top of the LOB. Base legs units
        REF_MARGIN_BID any number, representing the spread to keep from bid side of the reference market's bid price. We don't allow the price to go above the reference's market bid price minus REF_MARGIN_BID (negative is more aggressive). Basis points
        REF_MARGIN_ASK any number, representing the spread to keep from the ask side of a reference market's ask price. We don't allow the price to go below the reference's market ask price plus REF_MARGIN_ASK (negative is more aggressive). Basis points
        MIN_SPREAD - non-negative number, representing the minimal spread to be kept between our own best-bid and best-ask, in basis points
        MAX_SPREAD - non-negative number, representing the maximal spread to keep between our own best-bid and best-ask, in basis points
        TOP_SHIFT number, the price (quote leg units) shift to put a new order  relative to the top of the book. Positive yield a more aggressive price than the top of the book and negative a less aggressive one
        TOP_SHIFT_NOISE_WIDTH - two limits of a uniformly distributed sample are placed at:
        TOP_SHIFT + TOP_SHIFT_NOISE_WIDTH/2 and 
        TOP_SHIFT TOP_SHIFT_NOISE_WIDTH/2
        The sampled number is added to the TOP_SHIFT to calculate a final and random shift from the top of the book to place an order at such that the price of a new order is: top of the book +/- TOP_SHIFT + (uniformly sampled number between the two limits)
        ALGO_MODE one of: 
            BBBA - try to stay on top for both best-bid and best-ask
            BB - try to stay on top for best-bid only, in case BBBA leads to tighter spread then MIN_SPREAD
            BA - try stay on top for best-ask only, in case BBBA leads to tighter spread then MIN_SPREAD
        PARAMETERS CONSTRAINTS:
            1. MIN_SPREAD > 0, MAX_SPREAD > 0
            2. TOP_SHIFT_NOISE_WIDTH < 2*TOP_SHIFT
            3. MAX_SPREAD > MIN_SPREAD

    """

    def __init__(self, algotrade: AlgoTrade, config: dict, price_q: asyncio.Queue):
        """
        Args:
            algotrade: the AlgoTrade main object
            price_server: a running price source server for to place orders according to by an external service
            config: configuration dict
        """
        self._ref_price: dict[Side, float] = {}
        self._book = L2OrderBook()  # empty
        self._own_orders = L2OrderBook()  # empty
        self._algotrade = algotrade
        self._price_q = price_q

        # config params:
        self._max_spread = config['max_spread']
        self._order_amount = config['order_amount']
        self._refresh_amount = config['refresh_amount']
        self._top_shift = config['top_shift']
        self._noise_half_width = config['top_shift_noise_width'] / 2
        self._ref_margin = {Side.BUY: config['ref_margin_bid'] , Side.SELL: config['ref_margin_ask']}
        self._algo_mode = config['algo_mode']
        
    
    async def on_quote_update(self, update: Quote):
        """
        Reference price source is an OTC-like price source. When it provides an 
        update, that means the reference price update
        """
        self._set_ref_price(Side.BUY, update.bid_price)
        self._set_ref_price(Side.SELL, update.ask_price)
        await self._iterate()
        

    async def on_order_update(self, update: OrderStatusUpdate):
        if update.order:
            order = update.order
        else:
            order = self._algotrade.get_order(update.uuid)
        bids, asks = {}, {}
        if order.side is Side.SELL:
            asks[order.limit_price] = order.size
        else:
            bids[order.limit_price] = order.size
        self._own_orders.update(bids=bids, asks=asks)

    
    def _own_best(self, side: Side) -> tuple[float, float]:
        return self._own_orders.get_tob(side)

    def _set_ref_price(self, side: Side, price: float):
        self._ref_price[side] = price
        
    
    def _update_own_orders(self, bids: dict[float, float], asks: dict[float, float]):
        """
        Own orders may be converted to an L2OrderBook Object, after a bulk orders update
        """
    def get_noise(self):
        return random.uniform(-self._noise_half_width, self._noise_half_width)


    def _ref_price_initialized(self):
        return Side.SELL in self._ref_price and Side.BUY in self._ref_price

    def _book_initialized(self):
        return self._has_tob(self._book)

    def _own_orders_initialized(self):
        return self._has_tob(self._own_orders)

    def _has_tob(self, booklike: L2OrderBook):
        return booklike.has_tob(Side.SELL) and booklike.has_tob(Side.BUY)

    async def _iterate(self):
        """
        The algo iteration. Pushes a 
        """
        prices = {}
        if not self._ref_price_initialized() or not self._book_initialized() or not self._own_orders_initialized():
            return
        for side in Side:
            d = diff(self._book, self._own_orders)
            own_best = self._own_best(side)[0]  # the price only
            price = None
            tob = d.get_tob(side)[0]  # the price only
            if abs(tob - own_best) > self._top_shift or SIGN[side]*(tob - SIGN[side]*own_best) > 0:
                price = tob + SIGN[side]*(self._top_shift + self.get_noise())
            else:
                price = own_best
            price = EXTREME[side](price, self._ref_price[side]*(1 - SIGN[side]*self._ref_margin[side]))  # enforcing the ref mrgin
            prices[side] = price
        to_push = {}
        for side in prices.keys():
            to_push['bid' if side == Side.BUY else 'ask'] = prices[side]
        await self._price_q.put(to_push)

    async def on_book_update(self, update: BookUpdate):
        self._book.update(bids=update.bids, asks=update.asks)
        await self._iterate()
            