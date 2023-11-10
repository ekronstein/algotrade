import asyncio
import random
import websockets
import json
from datetime import datetime


SUPPORTED_PAIRS = set(['btc-eur', 'btc-usd'])
PORT = 8765
IP = '3.123.233.47'

class PriceServer:
    def __init__(self, price_q: dict[str, asyncio.Queue]):
        self._stop = asyncio.Future()
        self.received_payloads = set()
        self._price_q = price_q
        self.done_handler = lambda: ...

    async def stream(self, ws):
        """
        Args:
            ws a websocket object
        """
        while True:
            payload: dict[str, str] = json.loads(await ws.recv())
            for key, val in payload.items():
                payload[key.lower()] = val
            if 'subscribe' not in payload:
                await ws.send("invalid subscription message. Format should be: {\"subscribe\": \"base_currency-quote_currency\"}")
                continue
            if payload['subscribe'].lower() not in SUPPORTED_PAIRS:
                await ws.send(f'unsupported pair: { payload["subscribe"] }')
                continue
            break
        pair = payload['subscribe']
        while True:
            price = await self._price_q[pair].get()  # price expected to be a dict with both 'bid' and 'ask' as keys
            payload_str = json.dumps(
                {
                    pair:{
                        'bid': '{:0.8f}'.format(price['bid']),
                        'ask': '{:0.8f}'.format(price['ask'])
                    },
                    'timestamp': f'{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]}Z'
                }
            )  
            print(payload_str)
            await asyncio.sleep(random.uniform(0.2, 0.8))

    async def run(self):
        async with websockets.serve(self.stream, port=8765):  # type: ignore
            await asyncio.Future()  # run forever
        await asyncio.sleep(0.5)

async def random_price(pair: str, q: asyncio.Queue):
    while True:
        payload_str = json.dumps(
            {
                pair:{
                    'bid': '{:0.5f}'.format(random.uniform(19_900, 19_999)),
                    'ask': '{:0.5f}'.format(random.uniform(20_001, 21_100))
                },
                'timestamp': f'{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]}Z'
            }
        )  
        print(payload_str)
        await q.put(payload_str)
    

async def main():
    q = {'btc-eur':asyncio.Queue(), 'btc-usd': asyncio.Queue()}
    asyncio.gather(random_price('btc-eur', q['btc-eur']), random_price('btc-usd', q['btc-usd']))
    server = PriceServer(q)
    await server.run()
    
        
if __name__ == "__main__":
    asyncio.run(main())