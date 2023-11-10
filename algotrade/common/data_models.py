from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from uuid import UUID

from algotrade.common.enums import Currency, MarketName, Side


@dataclass(frozen=True)
class CurrencyPair: 
    leg1: Currency
    leg2: Currency
    def __repr__(self) -> str:
        return f"CurrencyPair: {self.leg1.value}-{self.leg2.value}"

    def __str__(self):
        return self.leg1.value.upper() + "-" + self.leg2.value.upper()


@dataclass(frozen=True)
class Update:
    pair: CurrencyPair
    market: MarketName


def currency_pair_from_str(pair: str) -> CurrencyPair:
    splt = pair.split('-')
    leg1 = Currency(splt[0].lower())
    leg2 = Currency(splt[1].lower())
    return CurrencyPair(leg1, leg2)


@dataclass(frozen=True)
class Quote:
    bid_price: float
    ask_price: float
    tob_bid_price: float
    tob_ask_price: float
    market: MarketName
    pair: CurrencyPair
    size: float  # TODO rid of the tob here (it's a temp fix. and ugly) and use size = 0 for tob indication
    timestamp: datetime





@dataclass
class Order:
    """
    attributes:
        uuid: the orders given unique id
        timestamp: time at which the order was sent by the connection module
        size: order size in base leg units - strictly positive
        pair: order's pair
        side: buy or sell
        limit_price: limit price in quote leg units, provided when the order is a limit order
        market: market at which the order is placed
        timeout: time after which
        filled_size: base leg quantity units - ranges between 0 and size, defaults to 0
        filled_amount: quote leg quantity units - ranges between 0 and final amount, defaults to 0
        cum_fee: sum of the fees paid in order's quote leg units - strictly non negative, defaults to 0
        live: state of the order. True if accepted by market and not yet filled, cancelled or rejected, false otherwise, defaults to False
    """

    uuid: UUID
    # timestamp: datetime
    size: float
    pair: CurrencyPair
    side: Side
    limit_price: float
    market: MarketName
    timeout: float | None = None
    filled_size: float = field(init=True, default=0.0)
    filled_amount: float = field(init=True, default=0.0)
    cum_fee: float = field(init=True, default=0.0)
    live: bool = field(init=True, default=False)
    
    def __hash__(self):
        return hash(self.uuid)

    def size_left(self):
        """
        returns:
            size left to fill in base leg units
        """
        return self.size - self.filled_size

    def rel_fill(self):
        return self.filled_size / self.size


class OrderStatusUpdateType(Enum):
        """
        expect REJECTED, CANCELED and DONE to be mutually exclusive
        """
        ACCEPTED = auto()
        TRADE = auto()
        REJECTED = auto()
        CANCELED = auto()
        DONE = auto()
        GENERAL_INFO = auto()

@dataclass(frozen=True)
class OrderStatusUpdate:
    """ 
    Args:
        order: an order object representing the new state of the order. When not None,
        assume there is no Trade update for the same status update.

    """
    market: MarketName
    pair: CurrencyPair
    uuid: UUID
    update_type: OrderStatusUpdateType
    update_time: datetime
    reject_reason: str | None = None
    comment: str | None = None
    size: float = 0
    cum_filled_size: float = 0 # the new filled size
    cum_filled_amount: float = 0
    cum_fees: float = 0
    side: Side | None = None
    limit_price: float = 0
    live: bool = True


    @property
    def order(self) -> Order | None:
        if not (self.size and self.side and self.limit_price and self.live):  # without these not enough info for creating an onject
            return None
        return Order(
            uuid=self.uuid,
            size=self.size,
            pair=self.pair,
            side=self.side,
            limit_price=self.limit_price,
            market=self.market,
            filled_size=self.cum_filled_size,
            filled_amount=self.cum_filled_amount,
            cum_fee=self.cum_fees,
            live=self.live
        )


@dataclass(frozen=True)
class Trade:
    """
    A Trade associated with an own-limit-order which is identified by uuid.
    Attributes:
        uuid: The uuid of the asociated order
        trade: Trade objects with trade details
    """
    uuid: UUID
    size: float
    amount: float
    fee: float


@dataclass(frozen=True)
class  BookUpdate:
    """
    An update of an L2 order book. For each changed price level on both bid and ask side, the price level is mapped to the
    corresponding new size at this level. Note that there should be no distinction between a partial book update and a full
    book snapshot.
    Attributes:
        pair: The corresponding currency pair
        market: The market the update came from
        bids: A map from bid price levels to new corresponding size at this price level. 
        bids: A map from ask price levels to new corresponding size at this price level. 
        timestamp: Time the update object was created or the time of the update supplied from the market. The earlier of the two.
    """
    pair: CurrencyPair
    market: MarketName
    bids: dict[float, float]
    asks: dict[float, float]
    timestamp: datetime | None = None
    snapshot: bool = False




