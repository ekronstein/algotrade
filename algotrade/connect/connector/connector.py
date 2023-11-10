import asyncio
import dataclasses
from random import uniform
from typing import Callable, Protocol

import websockets
from loguru import logger
from websockets.exceptions import ConnectionClosedError

from algotrade.common.enums import AdapterName, ConnectorTopic
from algotrade.pubsub import PubSub


class HeaderGenerator(Protocol):
    def get_headers(self) -> dict:
        """
        Returns extra headers for websockets connection - usually have to be signed
        """
        ...

@dataclasses.dataclass
class Connector:
    """
    class to handle market connection through a single websocket
    """

    def __init__(
        self,
        uri: str,
        adapter_name: AdapterName,
        ps: PubSub,
        generate_headers: Callable[..., dict] | None = None,
    ):
        """ 
            H+eader can be required to be dynamically generated and updated when reconnecting in case of a dissconnect            
            Returns the name of the adapter which the connector is communicating with
        """
        self._uri = uri
        self._out_q = asyncio.Queue()
        self._ps = ps
        self._generate_headers = generate_headers
        self._adapter_name = adapter_name
        self._connected = asyncio.Future()

    async def connect(self):
        i = 0
        while True:
            extra_headers = self._generate_headers() if self._generate_headers is not None else None # type: ignore
            try:
                async with websockets.connect(uri=self._uri, extra_headers=extra_headers) as ws:  # type: ignore
                    self._connected.set_result(True)
                    i = 0
                    # init_response = await ws.recv()
                    await self._ps.publish((ConnectorTopic.CONNECTION_ESTABLISHED, self._adapter_name), None)
                    await self._run_socket(ws)  # runs forever
            except (ConnectionClosedError, websockets.exceptions.InvalidStatusCode) as e:  # type: ignore
                sleep = uniform(0.3, 5)
                _log_disconnection_info(self._uri, extra_headers, sleep, i + 1, e)
                await asyncio.sleep(sleep)
                i += 1
            

    async def on_payload_out(self, payload):
        await self._out_q.put(payload)

    async def connected(self):
        return self._connected

    async def _run_socket(self, ws):
        await asyncio.gather(self._run_send(ws), self._run_recieve(ws))    

    async def _run_send(self, ws):
        while True:
            to_send = await self._out_q.get()
            await ws.send(to_send)
    
    async def _run_recieve(self, ws):
        while True:
            payload = await ws.recv()
            await self._ps.publish((ConnectorTopic.PAYLOAD_IN, self._adapter_name), payload)


def _log_disconnection_info(
    uri: str, 
    extra_headers: dict | None, 
    sleep: float, 
    attempt: int, 
    exception
):
    
    logger.info(f"exception: {exception}")
    logger.info(
        f"disconnected from url: {uri}, header: {extra_headers}. reconnecting in {sleep} \
                        seconds... attempt no. {attempt}")
