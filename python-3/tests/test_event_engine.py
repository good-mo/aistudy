import time
import pytest
from threading import Event as ThreadEvent
from stock.engine.event_engine import EventEngine, Event

import sys
print("\n--- sys.path >>>")
for p in sys.path:
    print(p)
print("--- end sys.path ---\n")

@pytest.fixture(scope="function")
def event_engine():
    engine = EventEngine()
    engine.start()
    yield engine
    engine.stop()

def test_register_and_unregister(event_engine):
    def handler(event):
        pass
    event_engine.register("type1", handler)
    assert "type1" in event_engine.handlers

    event_engine.unregister("type1", handler)
    assert "type1" not in event_engine.handlers