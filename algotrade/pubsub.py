
import asyncio
from typing import Callable, Coroutine, Hashable


class PubSub:
    EMPTY_STALL_TIME = 0.01
    def __init__(self) -> None:
        self._queues: dict[Hashable, asyncio.Queue] = {}
        self._consumed_msgs: dict[Hashable, asyncio.Queue] = {}
        self._consumers: dict[Hashable, list[Callable[..., Coroutine]]] = {}
        self._consumed: set = set()
        
    async def publish(self, qid: Hashable, data: object | None = None):
        """
        Adds an event to the qid channel
        Args:
            qid: event topic id
            data: data to be pushed to event q
        """
        q = self._init_qid(qid)
        await q.put(data)
    
    async def subscribe(self, qid: Hashable, handler: Callable[..., Coroutine]):
        """
        Adds a handler to the topic with id qid. The handler will be called along with all other subscribed handlers, when an event is availale
        Args:
            qid: event topic id
            handler: and `async def` function or any other Callable that returns a Corutine
        """
        self._consumers.setdefault(qid, []).append(handler)
        if qid not in self._consumed:
            await self._feed(qid)

    def _init_qid(self, qid: Hashable) -> asyncio.Queue:
        """
        Inits a new queue for an unseen qid or returns the queue for an existing one
        Args:
            qid:
        Returns: 
            the asyncio.Queue() asociated with the event id qid
        """
        if qid not in self._queues:
            # avoid set default to prevent multiple redundant calls to astncio.Queue()
            self._queues[qid] = asyncio.Queue()
        return self._queues[qid]

    def stop(self):
        self._consumed.clear()
        
    async def _feed(self, qid: Hashable):
        """
        Contiuously gets events in the asyncio.Queue asociated with the event id qid
        and feeds the consumers
        """      
        self._consumed.add(qid)
        q = self._init_qid(qid)
        while qid in self._consumed: 
            # try: 
            data = await q.get()
            coros = (consumer(data) for consumer in self._consumers[qid])
            # await asyncio.gather(*coros)  # await to not allow subsequent calls for the same worker to run concurrently 
            for coro in coros:
                await coro  # blocking
