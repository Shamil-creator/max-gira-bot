from pathlib import Path
import asyncio
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from handlers.add_new_water_meter_readings import add_new_mr_router
from handlers.meter_readings import meter_readings_router
from states.auth_states import Auth_States
from states.meter_redings_state import Meter_Readings_States


class FakeMemoryContext:
    def __init__(self, *, state=None, data=None):
        self._state = state
        self._data = dict(data or {})

    async def get_state(self):
        return self._state

    async def set_state(self, state=None):
        self._state = state

    async def get_data(self):
        return dict(self._data)

    async def set_data(self, data):
        self._data = dict(data)

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def clear(self):
        self._state = None
        self._data.clear()


class FakeRedis:
    def __init__(self):
        self.lists = {}
        self.values = {}

    async def lpush(self, key, *values):
        arr = self.lists.setdefault(key, [])
        for value in values:
            arr.insert(0, str(value))

    async def rpush(self, key, *values):
        arr = self.lists.setdefault(key, [])
        for value in values:
            arr.append(str(value))

    async def lrange(self, key, start, end):
        arr = self.lists.get(key, [])
        if end == -1:
            end = len(arr) - 1
        if end < start:
            return []
        return arr[start : end + 1]

    async def llen(self, key):
        return len(self.lists.get(key, []))

    async def delete(self, key):
        self.lists.pop(key, None)
        self.values.pop(key, None)

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value):
        self.values[key] = value

    async def lset(self, key, index, value):
        self.lists[key][index] = str(value)

    async def lrem(self, key, count, value):
        arr = self.lists.get(key, [])
        value = str(value)
        if count == 0:
            self.lists[key] = [item for item in arr if item != value]
            return
        removed = 0
        kept = []
        for item in arr:
            if item == value and removed < abs(count):
                removed += 1
                continue
            kept.append(item)
        self.lists[key] = kept


class FakeBot:
    def __init__(self):
        self._next_id = 1
        self._mid_to_id = {}
        self.sent_messages = []
        self.sent_photos = []
        self.deleted_messages = []

    def register_mid(self, mid):
        key = mid or f"synthetic:{self._next_id}"
        if key not in self._mid_to_id:
            self._mid_to_id[key] = self._next_id
            self._next_id += 1
        return self._mid_to_id[key]

    async def send_message(self, chat_id=None, text=None, reply_markup=None, parse_mode=None, attachments=None, **kwargs):
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
                "parse_mode": parse_mode,
                "attachments": attachments,
            }
        )
        return SimpleNamespace(message_id=self.register_mid(None))

    async def send_photo(self, chat_id=None, photo=None, caption=None, reply_markup=None, parse_mode=None, **kwargs):
        self.sent_photos.append(
            {
                "chat_id": chat_id,
                "photo": photo,
                "caption": caption,
                "reply_markup": reply_markup,
                "parse_mode": parse_mode,
            }
        )
        return SimpleNamespace(message_id=self.register_mid(None))

    async def delete_message(self, chat_id=None, message_id=None, **kwargs):
        self.deleted_messages.append((chat_id, message_id))
        return None

    async def edit_message_text(self, **kwargs):
        return None


class _Ctx:
    def __init__(self, state=None, data=None):
        self.ctx = FakeMemoryContext(state=state, data=data)

    async def get_state(self):
        return await self.ctx.get_state()

    async def set_state(self, state=None):
        await self.ctx.set_state(state)

    async def get_data(self):
        return await self.ctx.get_data()

    async def set_data(self, data):
        await self.ctx.set_data(data)

    async def update_data(self, **kwargs):
        await self.ctx.update_data(**kwargs)

    async def clear(self):
        await self.ctx.clear()


def _message_event(text: str, *, mid: str = "m1", user_id: int = 1, chat_id: int = 1):
    body = SimpleNamespace(text=text, mid=mid, attachments=[])
    sender = SimpleNamespace(user_id=user_id, username="u", full_name="User")
    recipient = SimpleNamespace(chat_id=chat_id)
    msg = SimpleNamespace(body=body, sender=sender, recipient=recipient)
    return SimpleNamespace(message=msg)


def _callback_event(payload: str, *, mid: str = "cb1", user_id: int = 1, chat_id: int = 1):
    body = SimpleNamespace(text="", mid=mid, attachments=[])
    sender = SimpleNamespace(user_id=user_id, username="u", full_name="User")
    recipient = SimpleNamespace(chat_id=chat_id)
    msg = SimpleNamespace(body=body, sender=sender, recipient=recipient)
    cb_user = SimpleNamespace(user_id=user_id, username="u", full_name="User")
    callback = SimpleNamespace(payload=payload, user=cb_user)

    async def answer(notification=None):
        return None

    return SimpleNamespace(message=msg, callback=callback, answer=answer)


def _install_fake_main(monkeypatch, *, redis, bot):
    fake_main = SimpleNamespace(redis=redis, bot=bot)
    monkeypatch.setitem(sys.modules, "main", fake_main)


def _last_text(bot: FakeBot):
    assert bot.sent_messages, "No messages were sent"
    return bot.sent_messages[-1]["text"]


def test_hot_water_number_valid_saved_and_wait_state(monkeypatch):
    fake_bot = FakeBot()
    fake_redis = FakeRedis()
    _install_fake_main(monkeypatch, redis=fake_redis, bot=fake_bot)
    add_new_mr_router._bot = fake_bot

    ctx = _Ctx(state=Meter_Readings_States.add_new_hot_water_readings)
    handled = asyncio.run(add_new_mr_router._dispatch_message(_message_event("12345"), ctx))

    assert handled is True
    assert asyncio.run(ctx.get_state()) == Meter_Readings_States.wait_hw_mr_state
    assert asyncio.run(fake_redis.lrange("user:1:list_hot_water", 0, -1)) == ["12345"]
    assert "Приняли ваш номер счетчика 12345" in _last_text(fake_bot)


def test_hot_water_number_rejects_non_digit(monkeypatch):
    fake_bot = FakeBot()
    fake_redis = FakeRedis()
    _install_fake_main(monkeypatch, redis=fake_redis, bot=fake_bot)
    add_new_mr_router._bot = fake_bot

    ctx = _Ctx(state=Meter_Readings_States.add_new_hot_water_readings)
    asyncio.run(add_new_mr_router._dispatch_message(_message_event("12a"), ctx))

    assert asyncio.run(fake_redis.lrange("user:1:list_hot_water", 0, -1)) == []
    assert _last_text(fake_bot) == "Введите пожалуйста число с счетчика, без других символов"


def test_hot_water_duplicate_checked_against_hot_list(monkeypatch):
    fake_bot = FakeBot()
    fake_redis = FakeRedis()
    fake_redis.lists["user:1:list_hot_water"] = ["777"]
    _install_fake_main(monkeypatch, redis=fake_redis, bot=fake_bot)
    add_new_mr_router._bot = fake_bot

    ctx = _Ctx(state=Meter_Readings_States.add_new_hot_water_readings)
    asyncio.run(add_new_mr_router._dispatch_message(_message_event("777"), ctx))

    assert asyncio.run(ctx.get_state()) == Meter_Readings_States.wait_hw_mr_state
    assert asyncio.run(fake_redis.lrange("user:1:list_hot_water", 0, -1)) == ["777"]
    assert "Вы уже ввели номер этого счетчика" in _last_text(fake_bot)


def test_wait_hot_state_without_button_prompts_user(monkeypatch):
    fake_bot = FakeBot()
    _install_fake_main(monkeypatch, redis=FakeRedis(), bot=fake_bot)
    add_new_mr_router._bot = fake_bot

    ctx = _Ctx(state=Meter_Readings_States.wait_hw_mr_state)
    asyncio.run(add_new_mr_router._dispatch_message(_message_event("любой текст"), ctx))

    assert _last_text(fake_bot) == "Пожалуйста нажмите одну из кнопок выше, чтоб мы могли продолжить⬆️"


def test_wait_cold_state_without_button_prompts_user(monkeypatch):
    fake_bot = FakeBot()
    _install_fake_main(monkeypatch, redis=FakeRedis(), bot=fake_bot)
    add_new_mr_router._bot = fake_bot

    ctx = _Ctx(state=Meter_Readings_States.wait_cw_mr_state)
    asyncio.run(add_new_mr_router._dispatch_message(_message_event("любой текст"), ctx))

    assert _last_text(fake_bot) == "Пожалуйста нажмите одну из кнопок выше, чтоб мы могли продолжить⬆️"


def test_callback_add_more_returns_to_hot_number_input(monkeypatch):
    fake_bot = FakeBot()
    _install_fake_main(monkeypatch, redis=FakeRedis(), bot=fake_bot)
    add_new_mr_router._bot = fake_bot

    ctx = _Ctx(state=Meter_Readings_States.wait_hw_mr_state)
    asyncio.run(add_new_mr_router._dispatch_callback(_callback_event("add_more"), ctx))

    assert asyncio.run(ctx.get_state()) == Meter_Readings_States.add_new_hot_water_readings
    assert _last_text(fake_bot) == "Пожалуйста напишите ещё один номер счетчика воды"


def test_callback_finish_input_shows_water_numbers(monkeypatch):
    fake_bot = FakeBot()
    fake_redis = FakeRedis()
    fake_redis.lists["user:1:list_hot_water"] = ["111", "222"]
    _install_fake_main(monkeypatch, redis=fake_redis, bot=fake_bot)
    add_new_mr_router._bot = fake_bot

    ctx = _Ctx(state=Meter_Readings_States.wait_hw_mr_state)
    asyncio.run(add_new_mr_router._dispatch_callback(_callback_event("finish_input"), ctx))

    text = _last_text(fake_bot)
    assert "Номера счетчиков на воду" in text
    assert "1) 111" in text
    assert "2) 222" in text


def test_callback_restart_clears_hot_water_list(monkeypatch):
    fake_bot = FakeBot()
    fake_redis = FakeRedis()
    fake_redis.lists["user:1:list_hot_water"] = ["111", "222"]
    _install_fake_main(monkeypatch, redis=fake_redis, bot=fake_bot)
    add_new_mr_router._bot = fake_bot

    ctx = _Ctx(state=Meter_Readings_States.wait_hw_mr_state)
    asyncio.run(add_new_mr_router._dispatch_callback(_callback_event("restart_mr_w"), ctx))

    assert asyncio.run(ctx.get_state()) == Meter_Readings_States.add_new_hot_water_readings
    assert asyncio.run(fake_redis.lrange("user:1:list_hot_water", 0, -1)) == []
    assert _last_text(fake_bot) == "Пожалуйста введите номер счетчика"


def test_callback_go_back_moves_to_menu(monkeypatch):
    import handlers.run as run_module

    fake_bot = FakeBot()
    _install_fake_main(monkeypatch, redis=FakeRedis(), bot=fake_bot)
    add_new_mr_router._bot = fake_bot
    async def _fake_build_menu_keyboard(_uid):
        return "menu-kb"

    monkeypatch.setattr(run_module, "build_menu_keyboard", _fake_build_menu_keyboard)

    ctx = _Ctx(state=Meter_Readings_States.add_new_hot_water_readings)
    asyncio.run(add_new_mr_router._dispatch_callback(_callback_event("add_hoc_go_back_cb"), ctx))

    assert asyncio.run(ctx.get_state()) == Auth_States.menu_state
    assert _last_text(fake_bot) == "Вы в меню"


def test_edit_hot_water_number_rejects_invalid_value(monkeypatch):
    fake_bot = FakeBot()
    fake_redis = FakeRedis()
    fake_redis.lists["user:1:list_hot_water"] = ["111", "333"]
    _install_fake_main(monkeypatch, redis=fake_redis, bot=fake_bot)
    add_new_mr_router._bot = fake_bot

    ctx = _Ctx(
        state=Meter_Readings_States.edit_mr_hw,
        data={"edit_mr_w": "333"},
    )
    asyncio.run(add_new_mr_router._dispatch_message(_message_event("77x"), ctx))

    assert asyncio.run(fake_redis.lrange("user:1:list_hot_water", 0, -1)) == ["111", "333"]
    assert _last_text(fake_bot) == "Введите пожалуйста число с счетчика, без других символов"


def test_edit_hot_water_number_rejects_duplicate(monkeypatch):
    fake_bot = FakeBot()
    fake_redis = FakeRedis()
    fake_redis.lists["user:1:list_hot_water"] = ["111", "333"]
    _install_fake_main(monkeypatch, redis=fake_redis, bot=fake_bot)
    add_new_mr_router._bot = fake_bot

    ctx = _Ctx(
        state=Meter_Readings_States.edit_mr_hw,
        data={"edit_mr_w": "333"},
    )
    asyncio.run(add_new_mr_router._dispatch_message(_message_event("111"), ctx))

    assert asyncio.run(fake_redis.lrange("user:1:list_hot_water", 0, -1)) == ["111", "333"]
    assert any("Вы уже ввели номер этого счетчика" in m["text"] for m in fake_bot.sent_messages)


def test_edit_hot_water_number_updates_selected_meter(monkeypatch):
    fake_bot = FakeBot()
    fake_redis = FakeRedis()
    fake_redis.lists["user:1:list_hot_water"] = ["111", "333"]
    _install_fake_main(monkeypatch, redis=fake_redis, bot=fake_bot)
    add_new_mr_router._bot = fake_bot

    ctx = _Ctx(
        state=Meter_Readings_States.edit_mr_hw,
        data={"edit_mr_w": "333"},
    )
    asyncio.run(add_new_mr_router._dispatch_message(_message_event("777"), ctx))

    assert asyncio.run(fake_redis.lrange("user:1:list_hot_water", 0, -1)) == ["111", "777"]
    assert "Номера счетчиков на воду" in _last_text(fake_bot)


def test_one_hot_water_state_replies_for_non_digit(monkeypatch):
    import handlers.run as run_module
    import handlers.excel_tg_test as excel_module

    fake_bot = FakeBot()
    _install_fake_main(monkeypatch, redis=FakeRedis(), bot=fake_bot)
    meter_readings_router._bot = fake_bot
    async def _fake_build_menu_keyboard(_uid):
        return "menu-kb"

    monkeypatch.setattr(run_module, "build_menu_keyboard", _fake_build_menu_keyboard)
    monkeypatch.setattr(run_module, "smart_keyboard_mr", lambda _: SimpleNamespace(inline_keyboard=[[]]))

    async def _fake_save(*args, **kwargs):
        return None

    monkeypatch.setattr(excel_module, "save_mr_result_in_excel", _fake_save)

    ctx = _Ctx(state=Meter_Readings_States.one_hot_water_readings_state)
    asyncio.run(meter_readings_router._dispatch_message(_message_event("abc"), ctx))

    assert _last_text(fake_bot) == "Пожалуйста введите число."


def test_one_cold_water_state_replies_for_non_digit(monkeypatch):
    import handlers.run as run_module
    import handlers.excel_tg_test as excel_module

    fake_bot = FakeBot()
    _install_fake_main(monkeypatch, redis=FakeRedis(), bot=fake_bot)
    meter_readings_router._bot = fake_bot
    async def _fake_build_menu_keyboard(_uid):
        return "menu-kb"

    monkeypatch.setattr(run_module, "build_menu_keyboard", _fake_build_menu_keyboard)
    monkeypatch.setattr(run_module, "smart_keyboard_mr", lambda _: SimpleNamespace(inline_keyboard=[[]]))

    async def _fake_save(*args, **kwargs):
        return None

    monkeypatch.setattr(excel_module, "save_mr_result_in_excel", _fake_save)

    ctx = _Ctx(state=Meter_Readings_States.one_cold_water_readings_state)
    asyncio.run(meter_readings_router._dispatch_message(_message_event("xyz"), ctx))

    assert _last_text(fake_bot) == "Пожалуйста введите число."
