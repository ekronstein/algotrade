from dataclasses import dataclass

from colorama import Fore

from algotrade.common.data_models import CurrencyPair, Quote
from algotrade.common.enums import MarketName
from algotrade.common.utils import calc_spread


@dataclass
class MinAskMaxBidData:
    """Use to store a crossed market situation data"""

    min_ask_mkt_data: Quote
    max_bid_mkt_data: Quote
    size: float

    def get_pair(self) -> CurrencyPair:
        return CurrencyPair(
            self.min_ask_mkt_data.pair.leg1, self.min_ask_mkt_data.pair.leg2
        )

    def get_min_ask_market_enum(self) -> MarketName:
        return self.min_ask_mkt_data.market

    def get_max_bid_market_enum(self) -> MarketName:
        return self.max_bid_mkt_data.market

    def get_min_ask_quote(self) -> Quote:
        return self.min_ask_mkt_data

    def get_max_bid_quote(self) -> Quote:
        return self.max_bid_mkt_data

    def get_min_ask(self) -> float:
        return self.min_ask_mkt_data.ask_price

    def get_max_bid(self) -> float:
        return self.max_bid_mkt_data.bid_price

    def __str__(self):
        ma, mb = self.min_ask_mkt_data, self.max_bid_mkt_data
        return f"Pair: {self.get_pair()}\n\
        Size: {self.size}\n\
        Min Ask: {ma.ask_price}, from {ma.market.value}, ts: {ma.timestamp}\n\
        Max Bid: {mb.bid_price}, from {mb.market.value}, ts: {mb.timestamp}\n\
        Spread: {calc_spread(mb.bid_price, ma.ask_price)}\n\
        {Fore.MAGENTA}Min Ask Market TOB bid - ask:  {ma.tob_bid_price} - {ma.tob_ask_price}\n\
        Max Bid Market TOB bid - ask:  {mb.tob_bid_price} - {mb.tob_ask_price}{Fore.RESET}\n"
