from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aiogram import Dispatcher


def test_dispatcher_bridge_handlers_require_context_annotation():
    dispatcher = Dispatcher()
    by_name = {
        handler.func_event.__name__: handler.func_event.__annotations__
        for handler in dispatcher._bridge_router.event_handlers
    }

    assert "context" in by_name["_on_message"]
    assert "context" in by_name["_on_callback"]
