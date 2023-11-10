import asyncio
from datetime import datetime
import toml
import pytest
from uuid import UUID, uuid4
from typing import Callable, Coroutine
import pytest_asyncio
from algotrade.algo.bbba.bbba import BBBA
from algotrade.common.enums import MarketName, Side, Currency

from algotrade.common.data_models import BookUpdate, CurrencyPair, OrderStatusUpdate, OrderStatusUpdateType, Quote, currency_pair_from_str




class AlgoTradeMock:

    def __init__(self):
        self.is_order_live_called = False
        self.publish_orders_called = False
        self.get_order_called = False
        self.cancel_orders_called = False

    async def subscribe_handler(self, update_topic: str, handler: Callable[..., Coroutine]):
        """
        Sets a handler Callable that returns a coroutine to be scheduled uppon an event of topic: update_topic.
        Args:
            update_topic: a string representing the event uppon which the handler is to be performed
                must be one of: `quote`, `book`, `order_status`, `trade`, `panic`
            handler: to be performed uppon the event represented by the update_topic string
        """
        ...

    def run(self):
        ...

    def is_order_live(self, uuid: UUID):
        self.is_order_live_called


class PriceServerMock():
    def __init__(self):
        self._published = set()
    
    async def publish_bbba(self, pair, bb, ba):
        self._published.add((pair, bb, ba))

    def get_published(self):
        return self._published

@pytest_asyncio.fixture
def algotrade_mock():
    yield AlgoTradeMock()

@pytest_asyncio.fixture
def config():
    with open('tests/configs/bbba.toml', 'r') as f:
        config = toml.load(f)['algos']['bbba']
    yield config

@pytest_asyncio.fixture
def base_book_update(market_pair):
    market, pair = market_pair
    yield BookUpdate(
        pair=pair,  # btc-eur
        market=market,  # bsdex
        bids={19_985:6_500, 19_988:2_300, 19_989:17_261, 19_990:10_000},
        asks={20_010:10_000, 20_011:1620, 20_015:10_570, 20_020:5_600},
    )


@pytest_asyncio.fixture
def bbbas_market_pairs_price_q(config: dict, algotrade_mock):
    market = MarketName('bsdex')
    config = config[market.value]
    pairs = config.keys()
    price_q = {pair: asyncio.Queue() for pair in pairs}
    yield {pair: BBBA(algotrade_mock, config[pair], price_q[pair]) for pair in pairs}, market, price_q

async def test_nothing_to_do(bbbas_market_pairs_price_q: tuple[dict[str, BBBA], MarketName, dict[str, asyncio.Queue]]):
    bbbas, market, price_q = bbbas_market_pairs_price_q
    pair_str = 'BTC-EUR'
    bbba = bbbas[pair_str]
    q = price_q[pair_str]
    pair = currency_pair_from_str(pair_str)
    book_update = BookUpdate(
        pair=pair,
        market=market,  # bsdex
        bids={19_985:6_500, 19_988:2_300, 19_989:17_261, 19_990:10_000},
        asks={20_010:10_000, 20_011:1620, 20_015:10_570, 20_020:5_600},
    )
    uuid = uuid4()
    await bbba.on_order_update(
        OrderStatusUpdate(
            market,
            pair,
            uuid,
            OrderStatusUpdateType.TRADE, 
            datetime.utcnow(), 
            size=10_000, 
            cum_filled_size=0,
            cum_fees=0,
            side=Side.BUY,
            limit_price=19_990,
            live=True
        )
    )

    await bbba.on_book_update(book_update)
    order_update = OrderStatusUpdate(
        market, 
        pair, 
        uuid, 
        OrderStatusUpdateType.TRADE, 
        datetime.utcnow(),
        size=10_000, 
        cum_filled_size=0,
        cum_fees=0,
        side=Side.SELL,
        limit_price=21_010,
        live=True
    )
    await bbba.on_order_update(order_update)
    assert bbba._own_best(Side.BUY) == (19990, 10000)
    assert bbba._own_best(Side.SELL) == (21010, 10000)
    assert q.empty()


@pytest.mark.asyncio
async def test_follow_down(bbbas_market_pairs_price_q: tuple[dict[CurrencyPair, BBBA], MarketName, dict[CurrencyPair, asyncio.Queue]]):
    bbba, market, price_q = bbbas_market_pairs_price_q
    pair = next(iter(bbba.keys()))
    bbba = bbba[pair]
    price_q = price_q[pair]
    uuid = uuid4()
    await bbba.on_order_update(
        OrderStatusUpdate(
            market,
            pair,
            uuid, 
            OrderStatusUpdateType.TRADE, 
            datetime.utcnow(), 
            size=10_000, 
            cum_filled_size=0,
            cum_fees=0,
            side=Side.BUY,
            limit_price=19_990,
            live=True
        )
    )
    await bbba.on_order_update(
        OrderStatusUpdate(
            market,
            pair, 
            uuid, 
            OrderStatusUpdateType.TRADE, 
            datetime.utcnow(), 
            size=10_000, 
            cum_filled_size=0,
            cum_fees=0,
            side=Side.SELL,
            limit_price=20010,
            live=True
        )
    )
    await bbba.on_book_update(
        BookUpdate(
            pair=pair,  # btc-eur
            market=market,  # bsdex
            bids={19_947:6_500, 19_948:2_300, 19_949:17_261, 19_990:10_000},
            asks={20_010:10_000, 20_011:1620, 20_015:10_570, 20_020:10_000},
        )
    
    )
    assert price_q.empty()
    await bbba.on_quote_update(
        Quote(
            bid_price=20005.0,
            ask_price=20005.0,
            tob_ask_price=20005.0,
            tob_bid_price=20005.0,
            market=market,
            pair=pair,
            size=0,
            timestamp=datetime.utcnow()
        )
    )
    assert not price_q.empty()
    print(await price_q.get())

if __name__ == "__main__":
    with open('tests/configs/bbba.toml', 'r') as f:
        _config = toml.load(f)
    print(_config)

