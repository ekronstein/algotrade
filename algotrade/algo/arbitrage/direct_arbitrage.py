from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from colorama import Fore
from loguru import logger

from algotrade.algo.arbitrage.direct_arbitrage_data_writer import \
    DirectArbitrageCSVWriter
from algotrade.algo.arbitrage.min_ask_max_bid import MinAskMaxBidData
from algotrade.algotrade import AlgoTrade
from algotrade.common.data_models import (BookUpdate, CurrencyPair, Order,
                                          Quote)
from algotrade.common.enums import MarketName, Side
from algotrade.common.utils import calc_spread


def shift_from_tob(mkt: Quote, aggressiveness: float):
    """
    returns:
        shift in quote leg units, from the top of the book to put limit orders in
    """
    return aggressiveness * (mkt.tob_ask_price - mkt.tob_bid_price)


@dataclass
class DirectArbitrageFinder:
    """Implements Algorithm protocol"""

    def __init__(self, trading: bool, algotrade: AlgoTrade, config: dict):
        self.trading = trading
        self._algo_trade = algotrade
        self._config = config
        self._market_order_threshold = config['algos']['direct_arbitrage']["market_order_threshold"]
        self._market_order_timeout = config['algos']['direct_arbitrage']["market_order_timeout"]
        self._quoting_period = config['algos']['direct_arbitrage']["quoting_period"]
        self._market_data: dict[CurrencyPair, dict[MarketName, Quote]] = {}
        self._last_mamb: dict[CurrencyPair, MinAskMaxBidData] = {}
        self._arb_live: set[CurrencyPair] = set()
        self._last_buysell: dict[CurrencyPair, tuple[Order, Order, datetime]] = {}
        self._writer = DirectArbitrageCSVWriter(config)
        self._aggressiveness = config['algos']['direct_arbitrage']["aggressiveness"]

    def _min_ask_max_bid(
        self, pair
    ) -> MinAskMaxBidData:  # TODO use priority q (sortedcontainers)
        min_ask, max_bid = float("inf"), -1
        min_ask_mkt, max_bid_mkt = None, None
        for mkt_data in self._market_data[pair].values():
            if mkt_data.bid_price > max_bid:
                max_bid = mkt_data.bid_price
                max_bid_mkt = mkt_data
            if mkt_data.ask_price < min_ask:
                min_ask = mkt_data.ask_price
                min_ask_mkt = mkt_data
        if min_ask_mkt is None or max_bid_mkt is None:
            raise ValueError
        return MinAskMaxBidData(min_ask_mkt, max_bid_mkt, min_ask_mkt.size)

    def _update_market_data(self, market_data: Quote):
        if market_data.pair not in self._market_data:
            self._market_data[market_data.pair] = {}
        self._market_data[market_data.pair][market_data.market] = market_data

    def _last_orders_filled(self, pair: CurrencyPair):
        """
        Checks whetehr both last buy and sell for `pair` are completely filled. 
        Returns:
            True if both orders are completely filled, False otherwise
        """
        if pair not in self._last_buysell:
            return True
        buy, sell, _ = self._last_buysell[pair]
        # if self._algo_trade.is_order_live(buy.uuid) or self._algo_trade.is_order_live(
        #     sell.uuid
        # ):
        #     return False
        # return True
        return not self._algo_trade.is_order_live(buy.uuid) and not self._algo_trade.is_order_live(sell.uuid)
            

    def _mamb_spread_changed(self, mamb: MinAskMaxBidData):
        return (
            not (mamb.get_pair() in self._last_mamb)
            or mamb.get_min_ask() != self._last_mamb[mamb.get_pair()].get_min_ask()
            or mamb.get_max_bid() != self._last_mamb[mamb.get_pair()].get_max_bid()
        )

    async def _reorder_or_skip(self, mamb: MinAskMaxBidData, spread: float):
        if self._last_orders_filled(mamb.get_pair()):
            buy, sell = self._calc_buysell_orders(mamb, spread)
            await self._publish_buy_sell_orders(buy, sell)
        elif (
            datetime.utcnow() - self._last_buysell[mamb.get_pair()][2]
        ).seconds > self._quoting_period:
            buy, sell, _ = self._last_buysell[mamb.get_pair()]
            await self._fill_with_market([buy.uuid, sell.uuid])  # if too long have passed close with market

    async def on_quote_update(self, mkt_data: Quote):
        """
        When new market data update arrives, decides according to minask maxbid spread
        whether to place buy-sell order pairs and of which type by emitting an event
        Args:
            mkt_data: used to update internal market data state that holds all current market quotes
        """
        self._update_market_data(mkt_data)
        mamb = self._min_ask_max_bid(mkt_data.pair)
        if self._mamb_spread_changed(mamb):
            self._last_mamb[mkt_data.pair] = mamb
            spread = calc_spread(mamb.get_max_bid(), mamb.get_min_ask())
            self._writer.add_line(mamb)
            logger.debug(mamb)
            if spread < self._config['algos']['direct_arbitrage']["arbitrage_threshold"]:
                if mkt_data.pair not in self._arb_live:
                    self._arb_live.add(mkt_data.pair)
                    logger.debug(Fore.CYAN + "Arbitrage started" + Fore.RESET)
                logger.debug(Fore.GREEN + "Arbitrage live" + Fore.RESET)

                await self._reorder_or_skip(mamb, spread)
            elif mkt_data.pair in self._arb_live:  # switch from live to dead
                self._arb_live.remove(mkt_data.pair)
                logger.debug(Fore.CYAN + "Arbitrage stopped" + Fore.RESET)
            else:
                logger.debug(Fore.RED + "Arbitrage Dead" + Fore.RESET)

    async def _publish_new_orders(self, orders: list[Order]):  # implements Algorithm Protocol
        """
        all orders assumed to be of the same pair and to the same market
        """
        if self.trading:
            await self._algo_trade.publish_orders(orders)
            

    async def _publish_buy_sell_orders(self, buy: Order, sell: Order):
        await self._publish_new_orders([buy, sell])
        # self._last_buysell[buy.pair] = (buy, sell, sell.timestamp)
        self._last_buysell[buy.pair] = (buy, sell, datetime.utcnow())
        

    def _create_limit_order(
        self,
        market: MarketName,
        pair: CurrencyPair,
        side: Side,
        size: float,
        limit_price: float,
    ):
        return Order(
            uuid=uuid4(),
            # timestamp=datetime.utcnow(),
            size=size,
            pair=pair,
            side=side,
            limit_price=limit_price,
            market=market,
            timeout=self._config["max_order_lifetime"],
        )

    def _calc_buysell_orders(
        self, data: MinAskMaxBidData, spread: float
    ) -> tuple[Order, Order]:
        mad = data.min_ask_mkt_data
        mbd = data.max_bid_mkt_data
        if spread < self._market_order_threshold:  # bp
            return (
                self._create_market_order(mad.market, mad.pair, Side.BUY, mad.size),
                self._create_market_order(mbd.market, mbd.pair, Side.SELL, mbd.size),
            )
        else:  # vanila limit order
            buy_lim = mad.tob_bid_price + shift_from_tob(mad, self._aggressiveness)
            sell_lim = mbd.tob_ask_price - shift_from_tob(mbd, self._aggressiveness)
            return (
                self._create_limit_order(
                    mad.market, mad.pair, Side.BUY, mad.size, buy_lim
                ),
                self._create_limit_order(
                    mbd.market, mbd.pair, Side.SELL, mbd.size, sell_lim
                ),
            )

    def _create_market_order(self, market: MarketName, pair: CurrencyPair, side: Side, size: float):
        """
        arguments:
            market: the market to place the order in
            pair: the order's currency pair
            side: buy or sell
            size: order size in base leg units
        returns:
            a new market order with a limit price deep in the book to ensure immediate execution
        note:
            the returned order is actually a hpyer aggressive limit order (in this apps terms it's aggressiveness is 1.2).
            the reason is that talos does not support a cancelreplace,
            which uses this function, with a limit order to be replaced by a market order. therefore,
            after a discussion with Bryan from talos, the solution is to put limit orders +-20% "into" the book,
            which is actually similar to what they are doing currently (9.7.2022)
        """
        market_data = self._market_data[pair][market]
        bid, ask = market_data.bid_price, market_data.ask_price
        rel_shift = 0.2
        price = bid * (1 + rel_shift) if side == Side.BUY else ask * (1 - rel_shift)
        return Order(
            uuid=uuid4(),
            # timestamp=datetime.utcnow(),
            size=size,
            pair=pair,
            side=side,
            market=market,
            limit_price=price,
            timeout=self._market_order_timeout,
        )

    async def _fill_with_market(self, uuids: list[UUID]):
        """
        emmits a cancelreplace of partially filled (0 to 1) order and replaces it with a market order for the remaining size (base leg) to fill.
        If the order is not anymore does nothing.
        notes:
            1. currently talos manages such an operation as a service, easy to use
            2. other exchanges do not support such an operation, then care must be taken to not send out an order before the cancelation of the live order is confirmed
            3. talos does not support a cancelreplace with a limit order to be replaced by a market order. therefore, after a discussion with Bryan from talos, the solution is to put limit orders +-20% "into" the book,
               which is the same as what they are doing internally (9.7.2022).
            4. the aggressivness parameter should be adjusted such that this funtion will be rarely called
        """
        if not self.trading:
            return
        new_ords = []
        for uuid in uuids:
            live_ord = self._algo_trade.get_order(uuid)
            new_ords.append(
                self._create_market_order(
                    live_ord.market, live_ord.pair, live_ord.side, live_ord.size_left()
                )
            )
        await self.cancel_orders(uuids)
        await self.publish_orders(new_ords)

    async def on_book_update(self, book_update: BookUpdate):
        pass

    async def on_panic(self):
        self.trading = False

    async def publish_orders(self, orders: list[Order]):
        await self._algo_trade.publish_orders(orders)

    async def cancel_orders(self, uuids: list[UUID]):
        await self._algo_trade.cancel_orders(uuids)
