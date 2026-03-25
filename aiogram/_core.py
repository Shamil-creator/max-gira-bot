from __future__ import annotations

import inspect
import itertools
import logging
import os
import shutil
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Optional

import aiohttp
from magic_filter import MagicFilter
from maxapi import Bot as MaxBot
from maxapi import Dispatcher as MaxDispatcher
from maxapi import Router as MaxRouter
from maxapi.enums.attachment import AttachmentType
from maxapi.enums.parse_mode import ParseMode as MaxParseMode
from maxapi.types.attachments.attachment import Attachment, ButtonsPayload, OtherAttachmentPayload
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.types.attachments.buttons.message_button import MessageButton
from maxapi.types.input_media import InputMedia, InputMediaBuffer

from .filters import StateFilter
from .filters.command import Command
from .fsm.context import FSMContext
from .fsm.state import State
from .types import BufferedInputFile, FSInputFile, InputFile

logger = logging.getLogger(__name__)
F = MagicFilter()


@dataclass
class _HandlerEntry:
    filters: tuple[Any, ...]
    func: Callable[..., Any]


class _SentMessage:
    def __init__(self, message_id: int, *, document_id: str | None = None, photo_id: str | None = None, video_id: str | None = None):
        self.message_id = message_id
        self.document = SimpleNamespace(file_id=document_id) if document_id else None
        self.photo = [SimpleNamespace(file_id=photo_id)] if photo_id else []
        self.video = SimpleNamespace(file_id=video_id) if video_id else None


class Bot:
    def __init__(self, token: str, session=None):
        self._max_bot = MaxBot(token=token)
        self.session = SimpleNamespace(close=self._max_bot.close_session)
        self._id_seq = itertools.count(1)
        self._mid_to_int: dict[str, int] = {}
        self._int_to_mid: dict[int, str] = {}
        self._synthetic_file_seq = itertools.count(1)

    def synthetic_file_id(self) -> str:
        return f"max:file:{next(self._synthetic_file_seq)}"

    def register_mid(self, mid: Optional[str]) -> int:
        if mid is None:
            mapped = next(self._id_seq)
            fake = f"synthetic:{mapped}"
            self._mid_to_int[fake] = mapped
            self._int_to_mid[mapped] = fake
            return mapped
        if mid not in self._mid_to_int:
            mapped = next(self._id_seq)
            self._mid_to_int[mid] = mapped
            self._int_to_mid[mapped] = mid
        return self._mid_to_int[mid]

    def _resolve_mid(self, message_id: Any) -> str:
        if isinstance(message_id, int):
            return self._int_to_mid.get(message_id, str(message_id))
        if isinstance(message_id, str):
            return message_id
        return str(message_id)

    def _to_max_parse_mode(self, parse_mode):
        if parse_mode is None:
            return None
        value = getattr(parse_mode, "value", parse_mode)
        if not value:
            return None
        value_str = str(value).lower()
        if "html" in value_str:
            return MaxParseMode.HTML
        return MaxParseMode.MARKDOWN

    def _convert_reply_markup(self, reply_markup) -> list[Attachment]:
        if reply_markup is None:
            return []

        from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

        rows = []
        if isinstance(reply_markup, InlineKeyboardMarkup):
            for row in reply_markup.inline_keyboard:
                max_row = []
                for btn in row:
                    if getattr(btn, "callback_data", None):
                        max_row.append(CallbackButton(text=btn.text, payload=btn.callback_data))
                    else:
                        max_row.append(MessageButton(text=btn.text))
                rows.append(max_row)

        elif isinstance(reply_markup, ReplyKeyboardMarkup):
            for row in reply_markup.keyboard:
                max_row = [MessageButton(text=btn.text) for btn in row]
                rows.append(max_row)

        if not rows:
            return []

        return [Attachment(type=AttachmentType.INLINE_KEYBOARD, payload=ButtonsPayload(buttons=rows))]

    def _to_input_media(self, item: Any):
        if isinstance(item, (FSInputFile, InputFile)):
            return InputMedia(item.path)
        if isinstance(item, BufferedInputFile):
            return InputMediaBuffer(item.data, filename=item.filename)
        if isinstance(item, str) and os.path.exists(item):
            return InputMedia(item)
        return None

    async def _download_to_buffer(self, url: str, filename: str) -> "BufferedInputFile":
        """Скачать файл по URL и вернуть как BufferedInputFile для загрузки в MAX.
        
        Передаём filename С расширением — maxapi теперь умеет сохранять оригинальное
        расширение (xlsx, docx, pdf и т.д.) без дублирования.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.read()
        return BufferedInputFile(data, filename=filename)
    @staticmethod
    def _is_http_url(value: Any) -> bool:
        return isinstance(value, str) and value.startswith(("http://", "https://"))

    async def send_message(self, chat_id=None, text: str | None = None, reply_markup=None, parse_mode=None, attachments=None, **kwargs):
        max_attachments = []
        if attachments:
            max_attachments.extend(attachments)
        max_attachments.extend(self._convert_reply_markup(reply_markup))

        response = await self._max_bot.send_message(
            chat_id=int(chat_id) if chat_id is not None else None,
            text=text,
            attachments=max_attachments or None,
            parse_mode=self._to_max_parse_mode(parse_mode),
        )

        mid = None
        try:
            mid = response.message.body.mid
        except Exception:
            pass

        message_id = self.register_mid(mid)
        return _SentMessage(message_id)

    async def send_document(self, chat_id, document, caption: str | None = None, reply_markup=None, parse_mode=None, **kwargs):
        media = self._to_input_media(document)
        document_id = None
        max_attachments = self._convert_reply_markup(reply_markup)

        if media is not None:
            # BufferedInputFile или FSInputFile — загружаем через обычный путь
            max_attachments.insert(0, media)
            document_id = getattr(document, "path", None) or self.synthetic_file_id()

        elif isinstance(document, str) and self._is_http_url(document):
            # Это URL — скачиваем и заново загружаем в MAX
            try:
                fname = kwargs.get("filename") or "document.bin"
                doc_buf = await self._download_to_buffer(document, fname)
                media = self._to_input_media(doc_buf)
                max_attachments.insert(0, media)
                document_id = self.synthetic_file_id()
            except Exception as e:
                logger.warning("MAX bridge: failed to pre-download document: %s", e)
                max_attachments.insert(
                    0,
                    Attachment(type=AttachmentType.FILE, payload=OtherAttachmentPayload(url=document)),
                )
                document_id = document

        elif isinstance(document, str) and document:
            # Это токен MAX — используем AttachmentUpload напрямую (без перезагрузки)
            # MAX возьмёт файл из своего хранилища с оригинальным именем и расширением
            from maxapi.types.attachments.upload import AttachmentUpload, AttachmentPayload
            from maxapi.enums.upload_type import UploadType
            att_upload = AttachmentUpload(
                type=UploadType.FILE,
                payload=AttachmentPayload(token=document),
            )
            logger.debug("MAX bridge: sending document via token %r", document[:20])
            max_attachments.insert(0, att_upload)
            document_id = document

        else:
            text = (caption + "\n" if caption else "") + f"[Документ недоступен для MAX: {document}]"
            return await self.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

        response = await self._max_bot.send_message(
            chat_id=int(chat_id),
            text=caption,
            attachments=max_attachments,
            parse_mode=self._to_max_parse_mode(parse_mode),
        )

        mid = None
        try:
            mid = response.message.body.mid
            atts = response.message.body.attachments or []
            if atts and getattr(atts[0], "payload", None) is not None:
                document_id = getattr(atts[0].payload, "url", None) or document_id
        except Exception:
            pass

        message_id = self.register_mid(mid)
        return _SentMessage(message_id, document_id=str(document_id) if document_id else None)

    async def send_photo(self, chat_id, photo, caption: str | None = None, reply_markup=None, parse_mode=None, **kwargs):
        media = self._to_input_media(photo)
        attachments = self._convert_reply_markup(reply_markup)
        photo_id = None

        if media is not None:
            attachments.insert(0, media)
            photo_id = getattr(photo, "path", None) if hasattr(photo, "path") else self.synthetic_file_id()
        elif isinstance(photo, str) and self._is_http_url(photo):
            # Signed MAX URLs истекают — скачиваем байты сами и заливаем заново,
            # иначе MAX пытается скачать по устаревшей ссылке и падает с 400.
            try:
                buf = await self._download_to_buffer(photo, kwargs.get("filename") or "photo.jpg")
                attachments.insert(0, self._to_input_media(buf))
                photo_id = self.synthetic_file_id()
            except Exception as e:
                logger.warning("MAX bridge: cannot download photo for re-upload (%s). Sending as text.", e)
                text = (caption + "\n" if caption else "") + "[Фото недоступно — ссылка устарела]"
                return await self.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif isinstance(photo, str) and photo:
            # Остальные строки (не URL) — пробуем как есть через OtherAttachmentPayload
            attachments.insert(0, Attachment(type=AttachmentType.IMAGE, payload=OtherAttachmentPayload(url=photo)))
            photo_id = photo
        else:
            text = (caption + "\n" if caption else "") + f"[Фото недоступно для MAX: {photo}]"
            return await self.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

        response = await self._max_bot.send_message(
            chat_id=int(chat_id),
            text=caption,
            attachments=attachments,
            parse_mode=self._to_max_parse_mode(parse_mode),
        )
        mid = None
        try:
            mid = response.message.body.mid
            atts = response.message.body.attachments or []
            if atts and getattr(atts[0], "payload", None) is not None:
                photo_id = getattr(atts[0].payload, "url", None) or photo_id
        except Exception:
            pass
        message_id = self.register_mid(mid)
        return _SentMessage(message_id, photo_id=str(photo_id) if photo_id else self.synthetic_file_id())

    async def send_video(self, chat_id, video, caption: str | None = None, reply_markup=None, parse_mode=None, **kwargs):
        media = self._to_input_media(video)
        attachments = self._convert_reply_markup(reply_markup)
        video_id = None

        if media is not None:
            attachments.insert(0, media)
            video_id = getattr(video, "path", None) if hasattr(video, "path") else self.synthetic_file_id()

        elif isinstance(video, str) and video:
            attachments.insert(
                0,
                Attachment(type=AttachmentType.VIDEO, payload=OtherAttachmentPayload(url=video)),
            )
            video_id = video
        else:
            text = (caption + "\n" if caption else "") + f"[Видео недоступно для MAX: {video}]"
            return await self.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

        response = await self._max_bot.send_message(
            chat_id=int(chat_id),
            text=caption,
            attachments=attachments,
            parse_mode=self._to_max_parse_mode(parse_mode),
        )
        mid = None
        try:
            mid = response.message.body.mid
            atts = response.message.body.attachments or []
            if atts and getattr(atts[0], "payload", None) is not None:
                video_id = getattr(atts[0].payload, "url", None) or video_id
        except Exception:
            pass
        message_id = self.register_mid(mid)
        return _SentMessage(message_id, video_id=str(video_id) if video_id else self.synthetic_file_id())

    async def send_media_group(self, chat_id, media, message_thread_id=None, **kwargs):
        sent = []
        for item in media:
            if hasattr(item, "media") and item.__class__.__name__.endswith("Photo"):
                sent.append(await self.send_photo(chat_id=chat_id, photo=item.media, caption=getattr(item, "caption", None)))
            elif hasattr(item, "media") and item.__class__.__name__.endswith("Video"):
                sent.append(await self.send_video(chat_id=chat_id, video=item.media, caption=getattr(item, "caption", None)))
        return sent

    async def edit_message_text(self, chat_id, message_id, text: str, reply_markup=None, parse_mode=None, **kwargs):
        mid = self._resolve_mid(message_id)
        attachments = self._convert_reply_markup(reply_markup)
        try:
            result = await self._max_bot.edit_message(
                message_id=mid,
                text=text,
                attachments=attachments or None,
                parse_mode=self._to_max_parse_mode(parse_mode),
            )
            if result is None:
                logger.warning(
                    "MAX bridge: edit_message_text returned no result chat_id=%r message_id=%r mid=%r",
                    chat_id,
                    message_id,
                    mid,
                )
        except Exception as e:
            # Keep compatibility (do not raise), but surface enough context
            # to debug "handler matched but message was not updated" cases.
            logger.exception(
                "MAX bridge: edit_message_text failed chat_id=%r message_id=%r mid=%r parse_mode=%r: %s",
                chat_id,
                message_id,
                mid,
                parse_mode,
                e,
            )

    async def delete_message(self, chat_id, message_id, **kwargs):
        mid = self._resolve_mid(message_id)
        try:
            await self._max_bot.delete_message(message_id=mid)
        except Exception:
            return None

    async def delete_webhook(self, drop_pending_updates=True):
        return None

    async def get_chat(self, chat_id):
        try:
            chat = await self._max_bot.get_chat_by_id(chat_id=int(chat_id))
            username = getattr(chat, "username", None)
            return SimpleNamespace(username=username)
        except Exception:
            return SimpleNamespace(username=None)

    async def get_file(self, file_id):
        # Telegram compatibility: handlers expect object with `file_path`.
        return SimpleNamespace(file_path=str(file_id))

    async def download_file(self, file_path, destination):
        file_path = str(file_path)
        destination = str(destination)
        os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)

        if file_path.startswith(("http://", "https://")):
            async with aiohttp.ClientSession() as session:
                async with session.get(file_path) as resp:
                    resp.raise_for_status()
                    content = await resp.read()
            with open(destination, "wb") as f:
                f.write(content)
            return destination

        if os.path.exists(file_path):
            shutil.copyfile(file_path, destination)
            return destination

        raise FileNotFoundError(f"Unsupported MAX file reference: {file_path}")


class Router:
    def __init__(self):
        self._max_router = MaxRouter()
        self._bot: Bot | None = None
        self._message_handlers: list[_HandlerEntry] = []
        self._callback_handlers: list[_HandlerEntry] = []

    def message(self, *filters):
        def decorator(func):
            self._message_handlers.append(_HandlerEntry(filters=filters, func=func))
            return func

        return decorator

    def callback_query(self, *filters):
        def decorator(func):
            self._callback_handlers.append(_HandlerEntry(filters=filters, func=func))
            return func

        return decorator

    async def _dispatch_message(self, event, memory_context) -> bool:
        if self._bot is None:
            return False
        from aiogram import types as aiotypes

        message_obj = aiotypes.Message(self._bot, event.message)
        message_text = getattr(message_obj, "text", None)
        for handler in self._message_handlers:
            if await self._matches(handler.filters, message_obj, memory_context):
                logger.info("MAX bridge: message matched handler=%s text=%r", handler.func.__name__, message_text)
                await self._call(handler.func, message_obj, memory_context)
                return True
        return False

    async def _dispatch_callback(self, event, memory_context) -> bool:
        if self._bot is None:
            return False
        from aiogram import types as aiotypes

        callback_obj = aiotypes.CallbackQuery(self._bot, event)
        callback_data = getattr(callback_obj, "data", None)
        for handler in self._callback_handlers:
            if await self._matches(handler.filters, callback_obj, memory_context):
                logger.info("MAX bridge: callback matched handler=%s data=%r", handler.func.__name__, callback_data)
                await self._call(handler.func, callback_obj, memory_context)
                return True
        return False

    @staticmethod
    def _state_equals(current_state, expected) -> bool:
        return current_state == expected or str(current_state) == str(expected)

    async def _matches(self, filters: tuple[Any, ...], obj, memory_context) -> bool:
        current_state = await memory_context.get_state()

        for flt in filters:
            if isinstance(flt, StateFilter):
                if not any(self._state_equals(current_state, st) for st in flt.states):
                    return False
                continue

            if isinstance(flt, State):
                if not self._state_equals(current_state, flt):
                    return False
                continue

            if isinstance(flt, Command):
                text = (getattr(obj, "text", None) or "").strip()
                if not text:
                    return False
                token = text.split()[0]
                command = token.lstrip("/").split("@", 1)[0]
                if command != flt.command:
                    return False
                continue

            if isinstance(flt, MagicFilter):
                try:
                    if not flt.resolve(obj):
                        return False
                except Exception:
                    return False
                continue

        return True

    async def _call(self, func, event_obj, memory_context):
        fsm = FSMContext(memory_context)
        signature = inspect.signature(func)
        params = list(signature.parameters.keys())

        kwargs = {}
        for name in params[1:]:
            if name in {"state", "context"}:
                kwargs[name] = fsm
            elif name == "bot":
                kwargs[name] = self._bot

        await func(event_obj, **kwargs)


class _StartupRegister:
    def __init__(self, dispatcher: "Dispatcher"):
        self._dispatcher = dispatcher

    def register(self, func):
        self._dispatcher._on_startup = func


class Dispatcher:
    def __init__(self, bot=None, storage=None):
        self._max_dispatcher = MaxDispatcher()
        self._bridge_router = MaxRouter()
        self._routers: list[Router] = []
        self._on_startup = None
        self.startup = _StartupRegister(self)

        @self._bridge_router.message_created()
        async def _on_message(event: Any, context: Any):
            text = getattr(getattr(event, "message", None), "body", None)
            text = getattr(text, "text", None)
            for router in self._routers:
                handled = await router._dispatch_message(event, context)
                if handled:
                    return
            logger.info("MAX bridge: message ignored text=%r", text)

        @self._bridge_router.message_callback()
        async def _on_callback(event: Any, context: Any):
            data = getattr(getattr(event, "callback", None), "payload", None)
            for router in self._routers:
                handled = await router._dispatch_callback(event, context)
                if handled:
                    return
            logger.info("MAX bridge: callback ignored data=%r", data)

        @self._bridge_router.bot_started()
        async def _on_bot_started(event: Any, context: Any):
            user = getattr(event, "user", None)
            chat_id = getattr(event, "chat_id", None)
            synthetic_event = SimpleNamespace(
                message=SimpleNamespace(
                    sender=user,
                    recipient=SimpleNamespace(chat_id=chat_id, user_id=getattr(user, "user_id", None)),
                    body=SimpleNamespace(text="/start", mid=None, attachments=[]),
                )
            )
            for router in self._routers:
                handled = await router._dispatch_message(synthetic_event, context)
                if handled:
                    logger.info("MAX bridge: bot_started mapped to /start")
                    return
            logger.info("MAX bridge: bot_started ignored chat_id=%r user_id=%r", chat_id, getattr(user, "user_id", None))

    def include_router(self, router: Router):
        self._routers.append(router)

    def include_routers(self, *routers: Router):
        self._routers.extend(routers)

    async def start_polling(self, bot: Bot):
        for router in self._routers:
            router._bot = bot

        # Single MAX router avoids swallowing all updates by the first aiogram Router.
        self._max_dispatcher.include_routers(self._bridge_router)

        if self._on_startup is not None:
            @self._max_dispatcher.on_started()
            async def _startup():
                await self._on_startup()

        await self._max_dispatcher.start_polling(bot._max_bot)
