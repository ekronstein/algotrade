import asyncio
import time
from functools import partial
from typing import Callable, Coroutine, Hashable

import pytest
import pytest_asyncio
from colorama import Fore

from algotrade.pubsub import PubSub


@pytest_asyncio.fixture
def ps():
    yield PubSub()


def get_worker_func(qid: Hashable, color, wait: float, msgs: dict[Hashable, set]) -> Callable[..., Coroutine]:
    async def worker(msg: str):
        start = time.time()
        print(color + f"worker-{qid}, started" + Fore.RESET)
        print(color + f"worker-{qid}'s message is: {msg}" + Fore.RESET)
        msgs.setdefault(qid, set()).add(msg)
        await asyncio.sleep(wait)
        print(color + f"worker-{qid}, done in {time.time() - start} seconds" + Fore.RESET)
    return worker

async def another_worker(
    a, msg):
    print(f'first arg is {a}')
    print(f'another worker msg is {msg}')

@pytest.mark.asyncio
async def test_coro():
    ps = PubSub()
    # asyncio.gather(cp.subscribe(1, another_worker))
    # asyncio.gather(ps.subscribe(1, another_worker))


@pytest.mark.asyncio
async def test_three_consumers(ps: PubSub):
    
    wait = 0.1  # sec
    # start = time.time()
    start = time.perf_counter()
    qid = 1
    qid2 = 2
    msgs = {}
    asyncio.gather (
        ps.subscribe(qid, get_worker_func(qid, Fore.GREEN, wait, msgs)),
        ps.subscribe(qid, get_worker_func(qid, Fore.MAGENTA, wait, msgs)),
        ps.subscribe(qid, get_worker_func(qid, Fore.YELLOW, wait, msgs)),
        ps.subscribe(qid2, get_worker_func(qid2, Fore.YELLOW, wait, msgs)),
        ps.subscribe(qid2, partial(another_worker, 'A')),
    )
    asyncio.gather(
        ps.publish(qid, 'msg-1'),
        ps.publish(qid, 'msg-2'),
        ps.publish(qid2, 'msg-3'),
    )
    
    elappsed = time.perf_counter() - start
    assert elappsed < 1.5 * wait, "took too long to launch and forget workers"
    await asyncio.sleep(0.5)
    assert 'msg-1' in msgs[qid]
    assert 'msg-2' in msgs[qid]
    assert 'msg-3' in msgs[qid2]
    

# @pytest.mark.asyncio
# async def test_stop(cp):
#     qid = 1
#     wait = 0.1
#     cp.add_consumer(qid, get_worker_func(qid, Fore.MAGENTA, wait))
#     await asyncio.sleep(0.1)
#     coros = [cp.produce(qid, 'msg-stop-1'), cp.stop(qid), cp.produce(qid, 'msg-stop-1'), cp.stop(qid)]
#     asyncio.gather(*coros)
    