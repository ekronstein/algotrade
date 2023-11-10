import pytest


@pytest.fixture
def pubsub_events():
    msgs = {}
    def get_event_consumer(qid):
        async def consumer(msg):
            msgs.setdefault(qid, []).append(msg)
        return consumer
    yield msgs, get_event_consumer
