from typing import Callable, Coroutine
from uuid import UUID

from algotrade.broker import Broker
from algotrade.common.data_models import Order
from algotrade.common.enums import (AdapterName, AdapterTopic, BrokerTopic,
                                    ConnectorTopic)
from algotrade.config import get_config
from algotrade.connect.adapter.adapter import Adapter
from algotrade.connect.adapter.talos import Talos
from algotrade.connect.connector.connector import Connector
from algotrade.pubsub import PubSub

config = get_config()


def _adapters_have_unique_names(adapters: list[Adapter]):
        names = set()
        for adapter in adapters:
            if adapter.get_name() in names:
                return False
            names.add(adapter.get_name())
        return True


class AlgoTrade:
    """
    An object that is used to create a composite system of a Broker which communicates with some `Adapter` objects.
    This is a high level module that is supposed to be used by trading algorithms. It provieds with update events that can be consumed
    by providing a handler `Callable` for a desired event, and provides means of sending order placing related messages out.
    This object is intended to be singleton.
    """
    UPDATE_TOPICS = {
        'quote': BrokerTopic.QUOTE_UPDATE, 
        'book': BrokerTopic.BOOK_UPDATE, 
        'order_status': BrokerTopic.ORDER_STATUS_UPDATE,
        # 'trade': BrokerTopic.TRADE_UPDATE,
        'panic': BrokerTopic.PANIC
    }

    def __init__(self, config: dict | None = None):
        config = config if config is not None else get_config()
        ps = PubSub()  # create the global `PubSub` object
        adapters = self._create_adapters(ps, config)
        connectors = self._create_connectors(ps, adapters)
        broker = Broker(ps)
        self._subscribe_coros = self._subscribe_all(adapters, connectors, broker, ps)
        self._ps = ps
        self._connectors = connectors
        self._broker = broker

    def run(self):
        """
        Returns:
            A list of coroutines to run concurrently.
        """
        return self._subscribe_coros + [connector.connect() for connector in self._connectors]

    async def subscribe_handler(self, update_topic: str, handler: Callable[..., Coroutine]):
        """
        Sets a handler Callable that returns a coroutine to be scheduled uppon an event of topic: update_topic.
        Args:
            update_topic: a string representing the event uppon which the handler is to be performed
                must be one of:
                1. 'quote'
                2. 'book' 
                3. 'order_status'
                4. 'panic'
            handler: to be performed uppon the event represented by the update_topic string
        """
        await self._ps.subscribe(self.UPDATE_TOPICS[update_topic], handler)

    def get_order(self, uuid: UUID) -> Order:
        return self._broker.get_order(uuid)

    async def cancel_orders(self, uuids: list[UUID]):
        await self._broker.cancel_orders(uuids)

    async def publish_orders(self, orders: list[Order]):
        await self._broker.publish_orders(orders)
    
    def is_order_live(self, uuid: UUID):
        return self._broker.is_order_live(uuid)

    def _adapters_markets_disjoint(self, adapters: list[Adapter]):
        """
        Return true only if no two adapters share a market they connect to.
        """
        markets = set()
        for adapter in adapters:
            for market in adapter.get_markets():
                if market in markets:
                    return False
                markets.add(market)
        return True
        
    def _create_adapters(self, ps: PubSub, config: dict) -> list[Adapter]:
        """
        Args:
            ps: global `PubSub` object
            config: global config dictionary with the same format as the default config.toml
        Returns:
            a list of `Adapter` objects in accordance with config, not yet subscribed to any `PubSub` events
        """
        res = []
        adapters_map = {AdapterName.TALOS: Talos}
        for adapter_str in config['adapters']['use']:
            adapter_name = AdapterName(adapter_str)
            res.append(adapters_map[adapter_name](ps, config))
        return res
        
    def _create_connectors(self, ps: PubSub, adapters: list[Adapter]):
        """
        Creates a list of connectors associated with a list of input adapters and a `PubSub` object to be used for later subscriptions
        Args:
            A list of adapters for which to create connectors for.
        Returns
            A list of connectors to be used by the input adapters. The i'th connector is created for the i'th adapter from the input list
        """
        return [
            Connector(
                adapter.get_uri(),
                adapter.get_name(),
                ps,
                adapter.generate_headers
            )
            for adapter in adapters
        ]
        
    def _create_adapters_connectors(self, ps: PubSub, config: dict):
        adapters = self._create_adapters(ps, config)
        connectors = self._create_connectors(ps, adapters)
        return adapters, connectors

    def _subscribe_adapters_connectors(self, adapters: list[Adapter], connectors:list[Connector], ps: PubSub) -> list[Coroutine]:
        coros = []
        for adapter, connector in zip(adapters, connectors):
            coros.append(ps.subscribe((AdapterTopic.PAYLOAD_OUT, adapter.get_name()), connector.on_payload_out))
            coros.append(ps.subscribe((ConnectorTopic.CONNECTION_ESTABLISHED, adapter.get_name()), adapter.on_connection_established))
            coros.append(ps.subscribe((ConnectorTopic.PAYLOAD_IN, adapter.get_name()), adapter.on_payload_recv_in))
        return coros

    def _subscribe_all(self, adapters: list[Adapter], connectors: list[Connector], broker: Broker, ps: PubSub) -> list[Coroutine]:
        coros = []
        coros += self._subscribe_adapters_connectors(adapters, connectors, ps)
        assert self._adapters_markets_disjoint(adapters)
        assert _adapters_have_unique_names(adapters)
        for adapter in adapters:
            for market in adapter.get_markets():
                # Broker -> Adapter (BrokerTopic, CurrencyPair, MarketName)
                # listen only to events relevent to the `Adapters` markets:
                coros.append(ps.subscribe((BrokerTopic.CANCEL_ORDERS_OUT, market), adapter.on_cancel_orders_out))
                coros.append(ps.subscribe((BrokerTopic.ORDERS_OUT, market), adapter.on_orders_out))
                # listen to all panic events:
                coros.append(ps.subscribe(BrokerTopic.PANIC, adapter.on_panic))
                    
        # Adapter -> Broker  
        coros.append(ps.subscribe(AdapterTopic.BOOK_UPDATE, broker.on_book_update))  # listen to all book update events
        coros.append(ps.subscribe(AdapterTopic.QUOTE_UPDATE, broker.on_quote_update))  # listen to all quote update events
        coros.append(ps.subscribe(AdapterTopic.ORDER_UPDATE, broker.on_order_update)) # listen to all order update events
        return coros    
