import pytest

from algotrade.algo.algorithm import Algorithm
from algotrade.algo.arbitrage.direct_arbitrage import DirectArbitrageFinder
from algotrade.common.data_models import CurrencyPair, Quote
from algotrade.common.enums import Currency, MarketName
from algotrade.config import get_config
from algotrade.pubsub import PubSub


class AlgoTradeMock:
    def __init__(self):
        self.publish_orders_called = False
        self.cancel_orders_called = False 

    def is_order_live(self, uuid):
        return True
    
    def get_order(self, uuid):
        return

    async def publish_orders(self, orders):
        self.publish_orders_called = True

    def cancel_orders(self, uuids):
        self.cancel_orders_called = True

    def clear(self):
        self.cancel_orders_called = False
        self.publish_orders_called = False

    def set_algorithm_handlers(self, algo: Algorithm):
        pass

    def set_handler(self, topic, handler):
        pass

    
@pytest.fixture
def daf():
    """
    daf - Direct Arbitrage Finder
    """
    config = get_config()
    config['dev'] = True
    config['algos']['direct_arbitrage']['arbitrage_threshold'] = -90
    algotrade_mock = AlgoTradeMock()
    ps = PubSub()
    daf = DirectArbitrageFinder(True, algotrade_mock, config)  # type: ignore
    yield daf, algotrade_mock, ps  # type: ignore

@pytest.fixture()
def test_market_data_updates():
    """
    Market data with "crossed arbitrage" (minask < maxbid) and without
    returns:
        market_data: a list of length 5 of MarketData
                     0-1, 0-4, 0-5 are not crossed beyond direct arbitrage threshgold (in config)
                     0-2, 0-3      are crossed beyond direct arbitrage threshgold (in config)
                     bids and asks of the market data elements look schematically like:
                     0         1         2         3          4          5
                     Kraken    Bitfinex  Bitstamp  Bitstamp   Bitstamp   Bitstamp
                                                   ___
                                         ___
                        
                               ___                 ___       
                                         ___                    
                     ___                                       ___        ___
               /               ___                           
market  spread       
               \\    ___                                       ___        ___


    """
    bidasks = ((100, 110), (105, 115), (111, 121),  (117, 127), (110.5, 121.5), (100, 110))
    markets = (MarketName.KRAKEN, MarketName.BITFINEX, MarketName.BITSTAMP, MarketName.BITSTAMP, MarketName.BITSTAMP ,MarketName.BITSTAMP)
    untested_args = (CurrencyPair(Currency.BTC, Currency.EUR), 1.0, None)
    market_data = []
    for bidask, market in zip(bidasks, markets):
        bid, ask = bidask[0], bidask[1]
        market_data.append(Quote(bid, ask, bid, ask, market, *untested_args))  # type: ignore
    yield market_data
    
@pytest.mark.asyncio
async def test_on_quote_update(daf: tuple[DirectArbitrageFinder, AlgoTradeMock, PubSub], test_market_data_updates):
    data_updates = test_market_data_updates
    algo, algotrade, _ = daf
    
    await algo.on_quote_update(data_updates[0])  # expected to emit cross spread update and no orders
    assert not algotrade.publish_orders_called, "no arbitrage - should not publish orders"
    
    algotrade.clear()
    await algo.on_quote_update(data_updates[1])  # expected to emit corss spread update
    
    await algo.on_quote_update(data_updates[2])
    assert data_updates[2].pair in algo._arb_live, f"arbitrage started: {data_updates[2].pair} must be in _arb_live"
    assert algotrade.publish_orders_called, "arbitrage live with no prev orders but new orders not published"

    algotrade.clear()
    await algo.on_quote_update(data_updates[3])  # expected to emit arb live and to emit orders out
    assert not algotrade.publish_orders_called, "arbitrage live with with prev orders live but orders published"
    assert data_updates[3].pair in algo._arb_live, f"arbitrage started: {data_updates[3].pair} must be in _arb_live"
    
    algotrade.clear()
    algo._algo_trade.is_order_live = lambda uuid: False  # ensures new orders are to be sent out regargless of previous ones
    await algo.on_quote_update(data_updates[2])  # cross spread update - arb live
    assert algotrade.publish_orders_called, "arbitrage live after cross spread update but no new orders published"
     
    algotrade.clear()
    await algo.on_quote_update(data_updates[4])
    assert data_updates[4].pair not in algo._arb_live, f"arbitrage stopped: {data_updates[4].pair} must not be in _arb_live"
    assert not algotrade.publish_orders_called, "arbitrage stopped but new orders published"

    algotrade.clear()
    await algo.on_quote_update(data_updates[2])  # cross spread update - arb live
    assert algotrade.publish_orders_called, "arbitrage live after cross spread update but no new orders published"

    algotrade.clear()
    await algo.on_quote_update(data_updates[5])
    assert data_updates[5].pair not in algo._arb_live, f"arbitrage stopped: {data_updates[5].pair} must not be in _arb_live"
    assert not algotrade.publish_orders_called, "arbitrage stopped but new orders published"






