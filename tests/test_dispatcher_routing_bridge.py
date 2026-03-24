from pathlib import Path
import asyncio
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command


class _Ctx:
    async def get_state(self):
        return None


def _message_event(text: str, mid: str = "m1"):
    body = SimpleNamespace(text=text, mid=mid, attachments=[])
    sender = SimpleNamespace(user_id=1, username="u", full_name="User")
    recipient = SimpleNamespace(chat_id=1)
    msg = SimpleNamespace(body=body, sender=sender, recipient=recipient)
    return SimpleNamespace(message=msg)


def _bridge_handler(dispatcher: Dispatcher, name: str):
    for handler in dispatcher._bridge_router.event_handlers:
        if handler.func_event.__name__ == name:
            return handler.func_event
    raise AssertionError(f"Bridge handler {name} not found")


def _bot_started_event(user_id: int = 1, chat_id: int = 1):
    user = SimpleNamespace(user_id=user_id, username="u", full_name="User")
    return SimpleNamespace(user=user, chat_id=chat_id)


def test_dispatcher_routes_to_next_router_if_first_not_matched():
    dp = Dispatcher()
    r1 = Router()
    r2 = Router()
    called = []

    @r1.message(F.text == "not_this")
    async def h1(message):
        called.append("r1")

    @r2.message(Command("start"))
    async def h2(message):
        called.append("r2")

    dp.include_routers(r1, r2)
    bot = Bot(token="test-token")
    for r in dp._routers:
        r._bot = bot

    on_message = _bridge_handler(dp, "_on_message")
    asyncio.run(on_message(_message_event("/start"), _Ctx()))

    assert called == ["r2"]


def test_dispatcher_stops_on_first_matching_router():
    dp = Dispatcher()
    r1 = Router()
    r2 = Router()
    called = []

    @r1.message(Command("start"))
    async def h1(message):
        called.append("r1")

    @r2.message(Command("start"))
    async def h2(message):
        called.append("r2")

    dp.include_routers(r1, r2)
    bot = Bot(token="test-token")
    for r in dp._routers:
        r._bot = bot

    on_message = _bridge_handler(dp, "_on_message")
    asyncio.run(on_message(_message_event("/start"), _Ctx()))

    assert called == ["r1"]


def test_command_filter_supports_bot_mention_suffix():
    router = Router()
    called = []

    @router.message(Command("start"))
    async def h(message):
        called.append("ok")

    router._bot = Bot(token="test-token")
    handled = asyncio.run(
        router._dispatch_message(_message_event("/start@id165004408714_bot"), _Ctx())
    )

    assert handled is True
    assert called == ["ok"]


def test_bot_started_is_mapped_to_start_message_flow():
    dp = Dispatcher()
    router = Router()
    called = []

    @router.message(Command("start"))
    async def h(message):
        called.append("start")

    dp.include_router(router)
    router._bot = Bot(token="test-token")

    on_bot_started = _bridge_handler(dp, "_on_bot_started")
    asyncio.run(on_bot_started(_bot_started_event(), _Ctx()))

    assert called == ["start"]
