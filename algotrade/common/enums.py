from enum import Enum


class EnumHashable(Enum):
    """
    Adds the enums class name to the hash in order to prevent identical hash
    for the same name of two different topics.  
    For example, AdapterName.BSDEX and MarketName.BSDEX would have had the same hash
    without inheriting modified hash functionality
    """
    def __hash__(self):
        return hash((self.__class__.__name__, self.value))

class MarketName(EnumHashable):
    KRAKEN = "kraken"
    BITFINEX = "bitfinex"
    B2V2 = "b2c2"
    BINANCE = "binance"
    COINBASE = "coinbase"
    BITSTAMP = "bitstamp"
    FTX = "ftx"
    BSDEX = 'bsdex'
    OKCOIN = 'okcoin'
    TALOS = 'talos'  # talos can be treated as a market

class AdapterName(EnumHashable):
    TALOS = 'talos'
    BSDEX = 'bsdex'
    BITFINEX = 'bitfinex'

# (AdapterTopic.Book_Update, pair, market, 'ADAPTER')
class Currency(EnumHashable):
    BTC = "btc"
    EUR = "eur"
    ETH = "eth"
    CAD = "cad"
    CHF = "chf"
    USD = "usd"

class OrderType(EnumHashable):
    LIMIT = 'limit'
    MARKET = 'market'
    STOP = 'stop'
    TAKE = 'take'

class TimeFormat(EnumHashable):
    ISO_8601_UTC = "%Y-%m-%dT%H:%M:%S.%fZ"
    ISO_8601_UTC8F = "%Y-%m-%dT%H:%M:%S.%8fZ"

class Side(EnumHashable):
    BUY = 'buy'
    SELL = 'sell'

# Event Topics:
class AdapterTopic(EnumHashable):
    BOOK_UPDATE = 'book_update'
    ORDER_UPDATE = 'order_update'
    BULK_ORDERS_UPDATE = 'bulk_orders_update'
    QUOTE_UPDATE = 'quote_update'
    # TRADE = 'trade'
    PAYLOAD_OUT = 'payload_out'

class BrokerTopic(EnumHashable):
    CANCEL_ORDERS_OUT = 'cancel_orders_out'
    ORDERS_OUT = 'orders_out'
    ORDER_STATUS_UPDATE = 'order_update'
    BOOK_UPDATE = 'book_update'
    QUOTE_UPDATE = 'quote_update'
    TRADE_UPDATE = 'trade_update'
    PANIC = 'panic'

class ConnectorTopic(EnumHashable):
    CONNECTION_ESTABLISHED = 'connection_established'
    PAYLOAD_IN = 'payload_in'

if __name__ == "__main__":
    print(hash(MarketName.TALOS))
    print(hash(AdapterName.TALOS))