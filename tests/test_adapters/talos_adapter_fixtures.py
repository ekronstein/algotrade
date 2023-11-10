import json
from dataclasses import dataclass

import pytest

from algotrade.config import get_config
from algotrade.connect.adapter.talos import Talos
from tests.common import event_emitting  # , config

config = get_config()

@pytest.fixture
def talos_adapter(event_emitting):
    emitter, events = event_emitting
    return Talos(emitter, pairs=config['pairs'], sizes=config['sizes'], trading=True), events

@pytest.fixture
def payloads():
    res = {}
    execution_reports = {
        'initial_report': json.dumps\
        (
            {
                "reqid": 8,
                "type": "ExecutionReport",
                "seq": 1,
                "initial": True,
                "ts": "2019-09-17T17:46:31.335714Z",
                "data": [
                    {
                        "AvgPx": "0",
                        "ClOrdID": "bffd1c40-dcc3-4817-b61c-4185912e99fa",
                        "CumFee": "0",
                        "CumQty": "0",
                        "ExecID": "8c233c08-da37-46f8-9a7a-84e39b61313d",
                        "ExecType": "New",
                        "LeavesQty": "0.10000000",
                        "OrdStatus": "New",
                        "OrdType": "Limit",
                        "OrderID": "d2a2189a-728c-4375-a3fc-e006552cc73c",
                        "OrderQty": "0.10000000",
                        "Price": "18100.00000",
                        "Side": "Sell",
                        "Currency": "BTC",
                        "AmountCurrency": "USD",
                        "Strategy": "Limit",
                        "SubmitTime": "2019-09-17T17:46:30.346080Z",
                        "Symbol": "BTC-USD",
                        "TimeInForce": "GoodTillCancel",
                        "Revision": 2,
                        "RequestUser": "User",
                        "TransactTime": "2019-09-17T17:46:30.407000Z"
                    }
                ]
            }
        ),
        
        'status_change': json.dumps\
        ( 
            {
                "reqid": 8,
                "type": "ExecutionReport",
                "seq": 3,
                "ts": "2019-09-17T17:46:33.244351Z",
                "data": [
                    {
                        "AvgPx": "0",
                        "ClOrdID": "a1ff52ed-1586-4b22-b199-292dad18c066",
                        "CumFee": "0",
                        "CumQty": "0",
                        "ExecID": "95b8ac71-189a-4764-b6d0-5f1bc75c2f92",
                        "ExecType": "Canceled",
                        "LeavesQty": "0",
                        "OrdStatus": "Canceled",
                        "OrdType": "Limit",
                        "OrderID": "d2a2189a-728c-4375-a3fc-e006552cc73c",
                        "OrderQty": "0.10000000",
                        "OrigClOrdID": "bffd1c40-dcc3-4817-b61c-4185912e99fa",
                        "Price": "18100.00000",
                        "Side": "Sell",
                        "Currency": "BTC",
                        "AmountCurrency": "USD",
                        "Strategy": "Limit",
                        "SubmitTime": "2019-09-17T17:46:30.346080Z",
                        "Symbol": "BTC-USD",
                        "TimeInForce": "GoodTillCancel",
                        "Revision": 3,
                        "RequestUser": "User",
                        "TransactTime": "2019-09-17T17:46:33.209000Z"
                    }
                ]
            }
        ),
        
        'fill': json.dumps\
        (
            {
                "reqid": 8,
                "type": "ExecutionReport",
                "seq": 3,
                "ts": "2019-09-17T17:46:33.244351Z",
                "data": [
                    {
                        "AvgPx": "0",
                        "ClOrdID": "a1ff52ed-1586-4b22-b199-292dad18c066",
                        "CumFee": "0",
                        "CumQty": "0",
                        "ExecID": "95b8ac71-189a-4764-b6d0-5f1bc75c2f92",
                        "ExecType": "Canceled",
                        "LeavesQty": "0",
                        "OrdStatus": "Canceled",
                        "OrdType": "Limit",
                        "OrderID": "d2a2189a-728c-4375-a3fc-e006552cc73c",
                        "OrderQty": "0.10000000",
                        "OrigClOrdID": "bffd1c40-dcc3-4817-b61c-4185912e99fa",
                        "Price": "18100.00000",
                        "Side": "Sell",
                        "Currency": "BTC",
                        "AmountCurrency": "USD",
                        "Strategy": "Limit",
                        "SubmitTime": "2019-09-17T17:46:30.346080Z",
                        "Symbol": "BTC-USD",
                        "TimeInForce": "GoodTillCancel",
                        "Revision": 3,
                        "RequestUser": "User",
                        "TransactTime": "2019-09-17T17:46:33.209000Z"
                    }
                ]
            }  
        ),
        
        'done_for_day': json.dumps\
        (
            {
                "reqid": 8,
                "type": "ExecutionReport",
                "seq": 9,
                "ts": "2019-09-18T03:04:07.560671Z",
                "data": 
                [
                    {
                        "AvgPx": "10221.90000",
                        "ClOrdID": "a0b4f6f5-5cb8-49db-956e-b65f3b3f98de",
                        "CumFee": "0.25554",
                        "CumQty": "0.01000000",
                        "ExecID": "4c86b624-f5b8-414c-858f-38c29fc09382",
                        "ExecType": "DoneForDay",
                        "FeeCurrency": "USD",
                        "LeavesQty": "0",
                        "OrdStatus": "DoneForDay",
                        "OrdType": "Limit",
                        "OrderID": "3aaad2dd-65ef-4ce8-98da-8af52a5b6f3e",
                        "OrderQty": "0.01000000",
                        "Price": "10000.00000",
                        "Side": "Sell",
                        "Currency": "BTC",
                        "AmountCurrency": "USD",
                        "Strategy": "Limit",
                        "SubmitTime": "2019-09-18T03:04:06.793459Z",
                        "Symbol": "BTC-USD",
                        "TimeInForce": "GoodTillCancel",
                        "Revision": 4,
                        "RequestUser": "User",
                        "TransactTime": "2019-09-18T03:04:06.895000Z"
                    }
                ]
            }
        ),
    }

    market_snapshot = {    
        "reqid": 5,
        "type": "MarketDataSnapshot",
        "seq": 1,
        "initial": True,
        "ts": "2019-09-16T14:54:41.272293Z",
        "data": 
        [
            {
                "Symbol": "BTC-USD",
                "DepthType": "VWAP",
                "LiquidityType": "Indicative",
                "ExchangeTime": "2019-09-16T14:54:41.252293Z",
                "SystemTime": "2019-09-16T14:54:41.262293Z",
                "Bids": [
                    {
                        "Price": "10148.66",
                        "VWAP": "10148.66",
                        "Size": "1.00000000"
                    },
                    {
                        "Price": "10148.00",
                        "VWAP": "10149.30",
                        "Size": "5.00000000"
                    },
                    {
                        "Price": "10146.20",
                        "VWAP": "10147.50",
                        "Size": "10.00000000"
                    }
                ],
                "Offers": [
                    {
                    "Price": "10149.16",
                    "VWAP": "10149.16",
                    "Size": "1.00000000"
                    },
                    {
                    "Price": "10151.49",
                    "VWAP": "10150.10",
                    "Size": "5.00000000"
                    },
                    {
                    "Price": "10151.80",
                    "VWAP": "10150.50",
                    "Size": "10.00000000"
                    }
                ],
                "Markets": {
                    "coinbase": {
                        "Status": "Online",
                        "ExchangeTime": "2019-09-16T14:54:41.252293Z",
                        "SystemTime": "2019-09-16T14:54:41.262293Z",
                    },
                    "gemini": {
                        "Status": "Stale",
                        "ExchangeTime": "2019-09-16T14:54:11.152293Z",
                        "SystemTime": "2019-09-16T14:54:11.162293Z",
                    }
                }
            }
        ]
    }
    
    res['execution_reports'] = execution_reports
    res['market_snapshot'] = market_snapshot
    yield res

    
    
    
    

