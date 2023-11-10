from typing import Protocol

from algotrade.common.data_models import (BookUpdate, OrderStatusUpdate, Trade,
                                          Quote)


class Algorithm(Protocol):

    async def on_quote_update(self, update: Quote):
        """
        To perform when an `OTC like` (no order book) volume weighted average price (VWAP) quote update is received. 
        For example when a Talos quote per size changes or an otc quote per size changes.
        """
        ...   

    async def on_book_update(self, update: BookUpdate):
        """
        To perform when an order-book state update is recieved
        """
        ...

    async def on_order_update(self, update: OrderStatusUpdate):
        """
        To perform when an order changes it's state
        """
        ...

    async def on_trade(self, update: Trade):
        """
        To perform on an OWN order trade event 
        """
        # TODO expand to all trades
        ...
    
    async def on_panic(self):
        ...
