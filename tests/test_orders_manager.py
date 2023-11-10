import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from algotrade.common.data_models import (CurrencyPair, Order,
                                          OrderStatusUpdate,
                                          OrderStatusUpdateType, Trade)
from algotrade.common.enums import BrokerTopic, Currency, MarketName, Side
from algotrade.orders_manager import (OrderOverFlowError, OrdersManager,
                                      TradeOnDeadOrderError)
# from tests.common import event_emitting
from algotrade.pubsub import PubSub
from tests.common import pubsub_events


@pytest_asyncio.fixture
def orders_manager():
    """

    """
    ps = PubSub()
    manager = OrdersManager(ps)
    yield manager, ps

@pytest_asyncio.fixture
def orders():
    size = 1.0
    untested_order_params =  { 
        'pair': CurrencyPair(Currency.BTC, Currency.EUR),
        'market': MarketName.KRAKEN,
        'limit_price': 1e4,
        'timeout': None,
        'size': size
    }
    dt = timedelta(seconds=1.0)  
    orders = [
        # Order(uuid=uuid4(), timestamp=datetime.utcnow(), side=Side.BUY, **untested_order_params),
        # Order(uuid=uuid4(), timestamp=datetime.utcnow(), side=Side.BUY, **untested_order_params),
        # Order(uuid=uuid4(), timestamp=datetime.utcnow() + dt, side=Side.SELL, **untested_order_params),
        # Order(uuid=uuid4(), timestamp=datetime.utcnow() + dt, side=Side.BUY, **untested_order_params),
        Order(uuid=uuid4(),  side=Side.BUY, **untested_order_params),
        Order(uuid=uuid4(),  side=Side.BUY, **untested_order_params),
        Order(uuid=uuid4(),  side=Side.SELL, **untested_order_params),
        Order(uuid=uuid4(),  side=Side.BUY, **untested_order_params),
    ]
    return orders

@pytest.mark.asyncio
async def test_normal_flow(orders: list[Order], orders_manager: tuple[OrdersManager, PubSub]):
    manager, _ = orders_manager
    # size, amount = 1, 1
    amount = 1
    fee = amount * 2 / 1e4
    ntrades = 3
    rel_fill = 1.0 / ntrades
    # normal order flow
    ord = orders[0]
    # stub_pair = CurrencyPair(Currency.BTC, Currency.ETH)
    trade = Trade(ord.uuid, rel_fill*ord.size, rel_fill*amount, fee)
    now = datetime.utcnow()
    manager.on_orders_out([ord])
    assert not manager.is_live(ord.uuid), "order not confirmed by market but is in a live state"
    assert orders[0].uuid in manager._orders, "order out event fired but manager doesn't know the order"
    await manager.on_order_update(OrderStatusUpdate(ord.market, ord.pair, ord.uuid, OrderStatusUpdateType.ACCEPTED, now, None, None))
    assert manager.is_live(ord.uuid), "accepted order update event fired but order is not live"
    for i in range(ntrades):
        curr_rel_filled = (i + 1)*rel_fill
        manager.on_trade_in(trade)
        assert manager.get_order(ord.uuid).filled_size ==  curr_rel_filled * ord.size, "order fill size is inconsistent with last trade"
        assert manager.get_order(ord.uuid).filled_amount == curr_rel_filled * amount, "order fill amount is inconsistent with last trade" 
        assert manager.get_order(ord.uuid).cum_fee == fee * (i + 1), "order cummulative fee is inconsistent with last trade"

@pytest.mark.asyncio
async def test_dead_order_condition(orders, orders_manager):
    # TODO: perhaps allow trade on an order not yet alive
    ord = orders[0]
    manager, _ = orders_manager
    manager.on_orders_out([ord])
    with pytest.raises(TradeOnDeadOrderError) as e_info:
        # this trade's order is not supposed to be live already, since no update event of it received back
        await manager.on_trade_in(Trade(ord.uuid, 1, 1, 1))    

@pytest.mark.asyncio
async def test_order_overflow(orders: list[Order], orders_manager: tuple[OrdersManager, PubSub]):
    ord = orders[0]
    manager, _ = orders_manager
    ord.filled_size = ord.size
    manager.on_orders_out([ord])
    await manager.on_order_update(OrderStatusUpdate(ord.market, ord.pair, ord.uuid, OrderStatusUpdateType.ACCEPTED, datetime.utcnow(), None, None))
    with pytest.raises(OrderOverFlowError) as e_info:
        # trade on a filled order should raise an OrderOverFlowError:
        manager.on_trade_in(Trade(ord.uuid, 0.1, 0, 0))

@pytest.mark.asyncio  
async def test_rejected_order_flow(orders: list[Order], orders_manager: tuple[OrdersManager, PubSub], pubsub_events):
    manager, ps = orders_manager
    msgs, get_event_consumer = pubsub_events
    sell = orders[1]
    buy = orders[2]
    manager.on_orders_out([buy, sell])
    await manager.on_order_update(OrderStatusUpdate(buy.market, buy.pair, buy.uuid, OrderStatusUpdateType.REJECTED, datetime.utcnow(), None, None))
    assert not manager.is_live(buy.uuid), "order rejected but is still live"

    panic_qid = (BrokerTopic.PANIC, buy.pair, buy.market)
    asyncio.gather(ps.subscribe(panic_qid, get_event_consumer(panic_qid)))
    await asyncio.sleep(0.1)
    assert panic_qid in msgs, "unfilled order rejected but panic event not published"
    
    await manager.on_order_update(OrderStatusUpdate(sell.market, sell.pair, sell.uuid, OrderStatusUpdateType.ACCEPTED, datetime.utcnow(), None, None))
    await manager.on_order_update(OrderStatusUpdate(sell.market, sell.pair, sell.uuid, OrderStatusUpdateType.CANCELED, datetime.utcnow(), None, None))
    assert not manager.is_live(sell.uuid), "order cancelled update event published but the order is still in a live state"