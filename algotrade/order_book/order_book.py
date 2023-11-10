from operator import neg
from typing import Tuple

from sortedcontainers import SortedDict

from algotrade.common.enums import Side


class OrderBookMissingLevelError(Exception):
    pass

comp = {Side.BUY: lambda a, b: a < b, Side.SELL: lambda a, b: a > b}


class L2OrderBook:
    def __init__(self):
        """
        Attributes:
            levels: a sorted dictionary that maps a price level to the size at this level
            tob: the two Top-Of-the-Book figures
        """
        self._levels = {Side.BUY: SortedDict(), Side.SELL: SortedDict(neg)}
        self._tob = {Side.BUY: float("-inf"), Side.SELL: float("inf")}

    def update(self, bids: dict[float, float]={}, asks: dict[float, float]={}, snapshot=False):
        assert bids or asks
        if snapshot:
            self._levels = {Side.BUY: SortedDict(bids), Side.SELL: SortedDict(neg, asks)}
        else:
            self._update(bids, Side.BUY)
            self._update(asks, Side.SELL)

    def delta_update(
        self, bid_deltas: dict[float, float] | SortedDict, 
        ask_deltas: dict[float, float] | SortedDict
    ):
        self._delta_update(bid_deltas, Side.BUY)
        self._delta_update(ask_deltas, Side.SELL)
    
    def subtract(
        self, 
        asks: dict[float, float] | SortedDict, 
        bids: dict[float, float] | SortedDict
    ):
        self._delta_update(asks, Side.BUY, -1)
        self._delta_update(bids, Side.SELL, -1)
        
    def has_tob(self, side: Side):
        return side in self._levels and len(self._levels[side]) != 0

    def _delta_update(self, deltas: dict[float, float], side: Side, sign=1):
        sd = self._levels[side]  # sorted dict of levels at side
        for level in deltas.keys():
            if level not in self._levels[side]:
                sd[level] = deltas[level]
            else:
                sd[level] += sign * deltas[level]
            if sd[level] < 0:
                raise ValueError(
                    f"Level size cannot become negative. Raised for level: {level}"
                )
            if sd[level] == 0:
                sd.pop(level)

    def get_level(self, side: Side, nth_from_top=1) -> Tuple[float, float]:
        """
        Returns the nth price level from the tob on side `side`
        Arguments:
            nth_from_top: the nth level from the top of the book to return data for
            side: Buy or Sell side of the book
        Returns:
            (price level, size at price level)
        """
        return self._levels[side].peekitem(index=-nth_from_top)  # type: ignore

    def get_size(self, side: Side, price_level: float):
        return self._levels[side].get(price_level, 0)
    
    def get_tob(self, side: Side) -> Tuple[float, float]:
        """
        Returns the price level data for the top of the book on side `side`
        Arguments:
            side: Buy or Sell side of the book
        Returns:
            (price level, size at price level)
        """
        return self.get_level(side)

    def bids(self):
        return self._levels[Side.BUY]
    
    def asks(self):
        return self._levels[Side.SELL]

    def _update_tob(self, side: Side):
        """
        Updates the TOB (Top-Of-the-Book)
        """
        sd = self._levels[side]
        tmp = sd.peekitem(index=-1)[0]
        if comp[side](self._tob[side], tmp):
            self._tob[side]  = tmp  # type: ignore

    def _update(self, update: dict[float, float], side: Side):
        """
        TODO: We can get more efficient here by scanning the keys to find the max/min.
        Currently logarithminc in num of levels - in _update_tob
        Args:
            update:
            side:
            snapshot:
        """
        if not update:
            return
        sd = self._levels[side]  # sd: sorted dict
        sd.update(update)
        for level in update.keys():
            if level <= 0:
                raise ValueError(f"level {level} must be positive")
            if sd[level] < 0:
                raise ValueError(f"size at level {level} must be non-negative")
            if sd[level] == 0:
                sd.pop(level)
        self._update_tob(side)

def copy(book: L2OrderBook) -> L2OrderBook:
    res = L2OrderBook()
    res._levels = {Side.BUY: book._levels[Side.BUY].copy(), Side.SELL: book._levels[Side.SELL].copy()}
    res._tob = {Side.BUY: book._tob[Side.BUY], Side.SELL: book._tob[Side.SELL]}
    return res

def diff(lhs: L2OrderBook, rhs: L2OrderBook) -> L2OrderBook:
    """
    Subtracts the rhs book from the lgs. Modifies lhs!
    The returned book is a reference to lhs
    This function will raise an exception if not all price levels in
    rhs are also present in lhs.
    Arguments:
        lhs: (Left Hand Side) the book to reduce from
        rhs: (Right Hand Side) the book to be reduced
    """
    res = copy(lhs)
    res.subtract(rhs.bids(), rhs.asks())
    return res