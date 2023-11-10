import asyncio
from uuid import UUID

import pytest
import pytest_asyncio
import websockets
from colorama import Fore

from algotrade.common.data_models import Order
from algotrade.common.enums import (AdapterName, AdapterTopic, ConnectorTopic,
                                    MarketName)
from algotrade.connect.connector.connector import Connector
from algotrade.pubsub import PubSub


class Server:
    def __init__(self):
        self._stop = asyncio.Future()
        self.received_payloads = set()
        self.done_handler = lambda: ...

    async def echo(self, websocket):
        for _ in range(self._n_serves):
            payload = await websocket.recv()
            print(f"< {Fore.RED + payload + Fore.RESET}")
            self.received_payloads.add(payload)
            await websocket.send(payload)
            print(f"> {Fore.RED + payload + Fore.RESET}")
        await asyncio.sleep(0.5)
        self.done_handler()

    def stop(self):
        self._stop.set_result('stopped')

    def set_done_handler(self, handler):
        self._done_handler = handler

    async def run(self, n_serves=3):
        self._n_serves = n_serves
        async with websockets.serve(self.echo, "localhost", 8765):  # type: ignore
            await asyncio.Future()  # run forever
        await asyncio.sleep(0.5)



class AdapterMock:
    def __init__(self, msgs: list[str], ps: PubSub):
        self._ps = ps
        self.i = 0
        self._msg_iter = iter(self.messages(msgs))    
        

    def get_markets(self) -> list[MarketName]:
        return []

    def get_name(self) -> AdapterName:
        return AdapterName.BITFINEX  # arbitrary - won't be used here

    async def on_orders_out(self, orders: list[Order]):
        """
        Translates new orders msg from the `Broker` to the correct payload and sends to the connector
        """
        pass
    
    async def on_cancel_orders_out(self, uuids: list[UUID]):
        """
        Translates a cancel-orders msg from the `Broker` to the correct payload and sends to the connector
        """
        pass

    async def on_payload_recv_in(self, payload: str):
        """
        To be performed uppon a new payload from the connector
        """
        print(Fore.MAGENTA + f'adapter received: {payload}' + Fore.RESET)
        await self._ps.publish((AdapterTopic.PAYLOAD_OUT, self.get_name()), next(self._msg_iter))

    def messages(self, msgs):
        for msg in msgs:
            yield msg

    async def on_connection_established(self, msg):
        """
        To be performed when the connector established a connection. Usualy send a subpsriiption msg back
        """
        await self._ps.publish((AdapterTopic.PAYLOAD_OUT, self.get_name()), next(self._msg_iter))

    async def on_panic(self, msg: str):
        """
        """
        pass

@pytest_asyncio.fixture
def server():
    server = Server()
    yield server


@pytest.mark.asyncio
async def test_connector(server: Server):
    msgs = ['msg-0', 'msg-1', 'msg-2']
    ps = PubSub()
    server.set_done_handler(ps.stop)
    adapt = AdapterMock(msgs, ps)
    name = adapt.get_name()
    con = Connector("ws://localhost:8765", name, ps)
    asyncio.gather(server.run(len(msgs)))
    subs = [
        ps.subscribe((ConnectorTopic.PAYLOAD_IN, name), adapt.on_payload_recv_in),
        ps.subscribe((ConnectorTopic.CONNECTION_ESTABLISHED, name), adapt.on_connection_established),
        ps.subscribe((AdapterTopic.PAYLOAD_OUT, name), con.on_payload_out),
    ]
    asyncio.gather(*subs)
    await asyncio.sleep(0.1)
    asyncio.gather(con.connect())
    await asyncio.sleep(0.1)
