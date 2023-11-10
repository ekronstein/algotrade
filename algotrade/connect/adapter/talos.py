import base64
import hashlib
import hmac
import json as json
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import toml
from loguru import logger

from algotrade.common.data_models import (CurrencyPair, OrderStatusUpdate,
                                          OrderStatusUpdateType, Trade,
                                          Quote)
from algotrade.common.enums import (AdapterName, AdapterTopic, Currency,
                                    MarketName, Side, TimeFormat)
from algotrade.common.idgenerator import generate_id
from algotrade.config import get_config
from algotrade.connect.adapter.adapter import Order
from algotrade.pubsub import PubSub


class TalosError(Exception):
    pass


class TalosDuplicateReqidError(TalosError):
    pass


class TalosInvalidReqError(TalosError):
    pass


class BadTalosResponseError(TalosError):
    pass

class UnKnownRejReasonError(Exception):
    pass


class Talos:
    """Implements Adapter"""
    
    PATH = "/ws/v1"
    SIDE_TO_TALOS = {Side.BUY: "Buy", Side.SELL: "Sell"}
    CCY_TO_TALOS = {
        Currency.BTC: "BTC",
        Currency.CAD: "CAD",
        Currency.CHF: "CHF",
        Currency.ETH: "ETH",
        Currency.EUR: "EUR",
        Currency.USD: "USD",
    }

    def __init__(
        self, 
        ps: PubSub, 
        config: dict
    ):
        """
        Args:
            ps: `PubSub` event broker
            config: a configuration dict with a mandatory structure (toml):
                
                # Markets assigned to this adapter. 
                # None of the markets listed is allowed to be assigend to another adapter
                
                assigned_markets = [ 'market-1', 'market-2', ...]
                env = 'sandbox'  # 'prod', 'prod_trade', 'sandbox'

                [user]
                sandbox = '...'
                prod = '...'
                prod_trade = '...'

                [api_key]
                sandbox = '...'
                prod = '...'
                prod_trade = '...'

                [sub_account]
                sandbox = '...'
                prod_trade = '...'

        """
        self._config = config if config else get_config()
        self._talos_config = self._config['adapters']['talos']
        self._api_key = self._talos_config['api_key'][self._config['env']]
        self._uri = "wss://" + self._get_host(self._is_sandbox()) + self.PATH
        self._ps = ps
        self._pairs = self._talos_config['quote']['pairs']
        self._sizes = [float(size) for size in self._talos_config['quote']['sizes']]
        self._live: set[str] = set()
        self._ccy_quote_res: int = 10
        self._trading: bool = (self._config['env'] == 'prod_trade')
        self._sessionid = ""
        self._sent_uuids: set[UUID] = set()
        self._name = AdapterName.TALOS
        self._to_connector_qid = (AdapterTopic.PAYLOAD_OUT, self._name)
        self._live_strings = set(['New', 'PartiallyFilled', 'PendingCancel'])
        if len(self._pairs) != len(self._sizes):
            raise ValueError("lengths of pairs and sizes list must equal")
        self._markets = [MarketName(str_name) for str_name in self._talos_config['markets']]
        with open('secrets.toml', 'r') as f:
            self._secrets = toml.load(f)['talos']

    def get_uri(self) -> str:
        return self._uri

    def get_markets(self) -> list[MarketName]:
        return self._markets

    def generate_headers(self) -> dict:
        return self._generate_timestamp_signed_header(self._is_sandbox())

    async def on_orders_out(self, orders: list[Order]):
        """Sends an oder msg to Talos when an external `order data ready` event from an algorithm is triggered"""
        if not self._trading:
            return
        for order in orders:
            self._sent_uuids.add(order.uuid)
        payload = self._get_orders_payload(orders)
        await self._ps.publish((AdapterTopic.PAYLOAD_OUT, self.get_name()), payload)

    def on_cancel_orders_out(self, uuids: list[UUID]):
        """ """
        self._get_cancel_orders_payload(uuids)

    async def on_cancel_replace_orders_out(
        self, orig_uuids: list[UUID], new_orders: list[Order]
    ):
        if not self._trading:
            return
        payload = self._get_cancel_replace_orders_paylaod(orig_uuids, new_orders)
        for ord in new_orders:
            self._sent_uuids.add(ord.uuid)
        await self._ps.publish(self._to_connector_qid, payload)

    async def on_connection_established(self, msg):
        payloads = [
            self._get_snapshot_subscription_payload(pair, size, generate_id())
            for pair, size in zip(self._pairs, self._sizes)
        ]
        for payload in payloads:
            await self._ps.publish(self._to_connector_qid, payload)
        payload = self._get_execution_report_subscription_payload()
        await self._ps.publish(self._to_connector_qid,  payload)

    def on_panic(self, msg: str):
        self._trading = False  # TODO better panic handling. might not be fatal. perhaps, remove the relevant exchagne

    async def on_payload_recv_in(
        self, payload: str
    ):  # with talos currently ASSUME only one market in each update when setting throtle to 1ns TODO verify
        paylaod = json.loads(payload)
        rtype = paylaod["type"]
        match rtype:
            case "MarketDataSnapshot":  # much more frequent than other messages makes match efficient
                await self._handle_quote_update_payload(paylaod)
            case "ExecutionReport":
                await self._handle_execution_report_payload(paylaod)
            case "hello":
                self._sessionid = paylaod["session_id"]
                logger.info("Talos says hello")
            case "error":
                self._handle_err_message(paylaod)
            case _:
                raise BadTalosResponseError

    def get_name(self):
        return self._name

    def _get_orders_payload_dict(
        self,
        orders: list[Order],
        cancel_replace=False,
        orig_uuids: list[UUID] | None = None,
    ):
        payload = {
            "type": "OrderCancelReplaceRequest" if cancel_replace else "NewOrderSingle",
            "data": [
                {
                    "ClOrdID": str(order.uuid),
                    "Markets": [order.market.value],
                    "OrdType": "Limit",
                    "OrderQty": order.size,
                    "Side": self.SIDE_TO_TALOS[order.side],
                    "Symbol": self.CCY_TO_TALOS[order.pair.leg1]
                    + "-"
                    + self.CCY_TO_TALOS[order.pair.leg2],
                    "TimeInForce": "GoodTillCancel",
                    "SubAccount": self._talos_config["sub_account"][self._talos_config["env"]],
                    "Price": order.limit_price,
                    "CancelSessionID": self._sessionid,
                }
                for order in orders
            ],
        }
        if orig_uuids:
            for i, uuid in enumerate(orig_uuids):
                payload["data"][i]["OrigClOrdID"] = str(uuid)
        now = datetime.utcnow()
        for i, order in enumerate(orders):
            if order.timeout:
                end = now + timedelta(seconds=order.timeout)
                payload["data"][i]["EndTime"] = end.strftime(
                    TimeFormat.ISO_8601_UTC.value
                )
            payload["data"][i]["TransactTime"] = now.strftime(
                TimeFormat.ISO_8601_UTC.value
            )
        return payload

    def _get_orders_payload(self, orders: list[Order]):
        return json.dumps(self._get_orders_payload_dict(orders))

    def _get_cancel_orders_payload(self, uuids: list[UUID]):
        return json.dumps(
            {
                "type": "OrderCancelRequest",
                "data": [
                    {
                        "ClOrdID": str(uuid4()),
                        "OrigClOrdID ": str(uuid),
                        "TransacTime": datetime.strftime(
                            datetime.utcnow(), TimeFormat.ISO_8601_UTC.value
                        ),
                    }
                    for uuid in uuids
                ],
            }
        )

    def _get_cancel_replace_orders_paylaod(
        self, orig_uuids: list[UUID], new_orders: list[Order]
    ):
        payload = self._get_orders_payload_dict(
            new_orders, cancel_replace=True, orig_uuids=orig_uuids
        )
        payload["Comments"] = "cancel replace"
        return json.dumps(payload)


    def _handle_err_message(self, payload: dict):
        errcode = payload["error"]["code"]
        match errcode:
            case 2:
                raise TalosDuplicateReqidError
            case 1:
                raise TalosInvalidReqError
            case _:
                raise TalosError

    async def _handle_quote_update_payload(self, payload: dict):
        """Handles a message of type MarketDataSnapshot from Talos"""
        stream = payload["data"][0]  # assumes length 1  TODO
        name = list(stream["Markets"])[0]
        if stream["Markets"][name]["Status"] != "Online":
            logger.info(
                "talos reports market {} status is: {}".format(
                    name, stream["Markets"][name]["Status"]
                )
            )
            return None
        name = next(iter(stream["Markets"].keys()))
        quote_update = Quote(
            bid_price=float(
                stream["Bids"][1]["VWAP"]
            ),  # assume here if the market is online talos sends non empty bids
            ask_price=float(stream["Offers"][1]["VWAP"]),
            tob_bid_price=float(stream["Bids"][0]["VWAP"]),
            tob_ask_price=float(stream["Offers"][0]["VWAP"]),
            market=MarketName(name),
            pair=self._currency_pair_from_talos_symbol(stream["Symbol"]),
            size=float(stream["Bids"][1]["Size"]),
            timestamp=datetime.strptime(
                stream["ExchangeTime"], TimeFormat.ISO_8601_UTC.value
            ),
        )
        await self._ps.publish(AdapterTopic.QUOTE_UPDATE, quote_update)

    def _currency_pair_from_talos_symbol(self, symbol: str):
        return CurrencyPair(
                Currency(symbol.split("-")[0].lower()),
                Currency(symbol.split("-")[1].lower()),
        )

    async def _handle_execution_report_payload(self, payload: dict):
        # TODO: UGLY FUNCTION!!! Make beautiful
        if not payload["data"]:
            return
        for data in payload["data"]:
            try:
                resd = {
                    "uuid": UUID(data["ClOrdID"]),
                    "update_time": datetime.strptime(
                        payload["ts"], TimeFormat.ISO_8601_UTC.value
                    ),
                }
                if resd["uuid"] not in self._sent_uuids:
                    continue
            except ValueError:  # bad hex format happens often due to other orders from the same account not using uuid4 TODO apply a filter, perhaps with 'group' field
                continue
            match data["ExecType"]:
                case "New":
                    resd["update_type"] = OrderStatusUpdateType.ACCEPTED
                case "Rejected":
                    resd["update_type"] = OrderStatusUpdateType.REJECTED
                    resd["reject_reason"] = data.get(
                        "OrdRejReason", "reject reason missing"
                    )
                    resd["comment"] = "talos order status is {}".format(data["OrdStatus"])  # type: ignore
                case "ReplaceRejected":  # TODO that's not good. implementation details
                    resd["update_type"] = OrderStatusUpdateType.GENERAL_INFO
                    resd["comment"] = "replace rejected"
                case "Canceled" | "Replaced":
                    resd["update_type"] = OrderStatusUpdateType.CANCELED
                case "DoneForDay":
                    resd["update_type"] = OrderStatusUpdateType.DONE
                case "Trade":
                    # trade = Trade(
                    #     resd["uuid"],
                    #     float(data["LastQty"]),
                    #     float(data["LastAmt"]),
                    #     float(data["LastFee"])
                    # )
                    resd["update_type"] = OrderStatusUpdateType.TRADE  # TODO recall the trade event
                case _:
                    resd["update_type"] = OrderStatusUpdateType.GENERAL_INFO
                    resd["comment"] = "talos order status is {}".format(data["OrdStatus"])  # type: ignore
            # resd['order']  self._create_order(payload)
            resd['size'] = data['OrderQty']
            resd['cum_filled_size'] = data['CumQty']
            resd['cum_filled_amount'] = data['CumAmt']
            resd['cum_fee'] = data['CumTalosFee']
            resd['side'] = data['Side'].lower()
            resd['live'] =  data['OrdStatus'] in self._live_strings
            update = OrderStatusUpdate(**resd)
            await self._ps.publish(AdapterTopic.ORDER_UPDATE, update)

        
    def _create_order(self, report_data: dict) -> Order:
        """
        Creates an `Order` object from a talos execution report.
        Args:
            report: A talos execution report json payload converted to a dictionary
        """
        live = (report_data['OrdStatus'] in set(['New', 'PartiallyFilled', 'PendingCancel']))
        markets = report_data['Markets']
        if len(markets) > 1:
            market = MarketName.TALOS  # aggregate book quotes will be considered Talos as the market
        else:
            market = MarketName(markets[0])
        return Order(
            uuid=report_data['ClOrdID'],
            # timestamp=datetime.strptime(report_data['AmountCurrency'], TimeFormat.ISO_8601_UTC.value),
            size=report_data['OrderQty'],
            pair=self._currency_pair_from_talos_symbol(report_data["Symbol"]),
            side=report_data['Side'],
            limit_price=report_data['Price'],
            market=market,
            filled_size=report_data['CumQty'],
            filled_amount=report_data['CumAmt'],
            cum_fee=report_data['CumTalosFee'],
            live=live
        )

    def _get_host(self,sandbox: bool) -> str:
        if sandbox:
            return "tal-43.sandbox.talostrading.com"
        return "tal-84.prod.talostrading.com"

    def _is_sandbox(self,) -> bool:
        return (self._config['env'] == 'sandbox')

    def _generate_timestamp_signed_header(self,sandbox) -> dict:
        api_secret = self._config["secrets"]["talos"][self._config["env"]]
        host = self._get_host(sandbox)
        utc_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000000Z")
        params = "\n".join(
            [
                "GET",
                utc_datetime,
                host,
                self.PATH,
            ]
        )
        hash = hmac.new(api_secret.encode("ascii"), params.encode("ascii"), hashlib.sha256)
        # hash.hexdigest()
        signature = base64.urlsafe_b64encode(hash.digest()).decode()
        header = {
            "TALOS-KEY": self._api_key,
            "TALOS-SIGN": signature,
            "TALOS-TS": utc_datetime,
        }
        return header


    def _get_snapshot_subscription_payload(self,pair: str, size: float, reqid: int, **kw) -> str:
        subscription_payload = {
            "reqid": reqid,
            "type": "subscribe",
            "streams": [
                {
                    "Throttle": "1ns",
                    "name": "MarketDataSnapshot",
                    "Symbol": pair,
                    "Markets": [name],
                    "SizeBuckets": [0, str(size)],
                    "FeeMode": "Taker",  # this does NOT include Talos fee
                }
                for name in self._config["default_markets"][pair]
            ],
        }
        return json.dumps(subscription_payload)


    def _get_execution_report_subscription_payload(self) -> str:
        resd = {
            "reqid": generate_id(),
            "type": "subscribe",
            "streams": [
                {"name": "ExecutionReport", "User": self._config['adapters']['talos']["user"][self._config["env"]], "SendMarkets": True}
            ],
        }
        return json.dumps(resd)



