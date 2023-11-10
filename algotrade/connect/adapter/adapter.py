from typing import Protocol
from uuid import UUID

from algotrade.common.data_models import CurrencyPair, Order
from algotrade.common.enums import AdapterName, MarketName
from algotrade.pubsub import PubSub


class Adapter(Protocol):
    """
    Translates payloads from external sources updates to the native AlgoTrade data models.
    Examples:
        1. A Talos `Adapter` is translating talos messages, from multiple markets supported by Talos, 
           to updates in the native AlgoTrade data models
        2. A BSDeX `Adapter` is translating only BSDeX messages to updates in the native AlgoTrade data models
    """

    def __init__(self, ps: PubSub, config: dict):
        ...

    def get_markets(self) -> list[MarketName]:
        """
        Returns all of the markets this adapter is communicating with
        """
        ...

    def get_pairs(self) -> dict[MarketName, set[CurrencyPair]]:
        """
        Returns all pairs supported by this adapter
        """
        ...

    def get_name(self) -> AdapterName:
        """
        Returns this `Adapters` name. Each `Adapter` object is assumed to have a unique name.
        """
        ...
    
    def get_uri(self) -> str:
        """
        Returns the uri this `Adapter` object is to be connected to via a `Connector`
        """
        ...
    
    def generate_headers(self) -> dict:
        """
        Generates extra_headers for websockets. Connect for use in the inital connection and reconnect. 
        In most cases it must contain authentication, depending on the external data source
        """
        ...

    async def on_orders_out(self, orders: list[Order]):
        """
        Translates `new orders` in native data models to the correct payload and sends to the `Connector`
        """
        ...
    
    async def on_cancel_orders_out(self, uuids: list[UUID]):
        """
        Translates 'cancel orders' native data models to the correct payload and sends to the `Connector`
        """
        ...

    async def on_payload_recv_in(self, payload: str):
        """
        To be performed uppon a new payload from the `Connector`
        """
        ...

    async def on_connection_established(self, msg):
        ...
        """
        To be performed when the connector established a connection. Usualy send a subpsription message back
        """

    async def on_panic(self, msg: str):
        """
        To be performed on a panic event        
        """
        ...
