from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .input_file import FSInputFile, InputFile, BufferedInputFile


class MessageEntity:
    pass


@dataclass
class InlineKeyboardButton:
    text: str
    callback_data: Optional[str] = None
    style: Optional[str] = None


@dataclass
class InlineKeyboardMarkup:
    inline_keyboard: list[list[InlineKeyboardButton]]
    resize_keyboard: bool = False


@dataclass
class KeyboardButton:
    text: str
    style: Optional[str] = None


@dataclass
class ReplyKeyboardMarkup:
    keyboard: list[list[KeyboardButton]]
    resize_keyboard: bool = False


@dataclass
class PhotoSize:
    file_id: str
    file_size: int = 0


@dataclass
class Document:
    file_id: str
    file_name: Optional[str] = None
    file_size: int = 0
    mime_type: Optional[str] = None


@dataclass
class Video:
    file_id: str
    file_size: int = 0


@dataclass
class User:
    id: int
    username: Optional[str] = None
    full_name: str = ""


@dataclass
class Chat:
    id: int


@dataclass
class InputMediaPhoto:
    media: Any
    caption: Optional[str] = None


@dataclass
class InputMediaVideo:
    media: Any
    caption: Optional[str] = None


class Message:
    def __init__(self, bot, max_message, callback_event=None):
        self._bot = bot
        self._max_message = max_message
        self._callback_event = callback_event

        sender = getattr(max_message, "sender", None)
        recipient = getattr(max_message, "recipient", None)
        body = getattr(max_message, "body", None)

        sender_id = getattr(sender, "user_id", 0) if sender else 0
        username = getattr(sender, "username", None) if sender else None
        full_name = getattr(sender, "full_name", "") if sender else ""

        chat_id = None
        if recipient is not None:
            chat_id = getattr(recipient, "chat_id", None)
            if chat_id is None:
                chat_id = getattr(recipient, "user_id", None)
        if chat_id is None:
            chat_id = sender_id

        self.from_user = User(id=int(sender_id), username=username, full_name=full_name)
        self.chat = Chat(id=int(chat_id))

        self.text = getattr(body, "text", None)
        self.caption = self.text

        self.message_id = self._bot.register_mid(getattr(body, "mid", None))
        self.message_thread_id = None

        self.photo: list[PhotoSize] = []
        self.document: Optional[Document] = None
        self.video: Optional[Video] = None

        self._parse_attachments(getattr(body, "attachments", []) or [])

    def _parse_attachments(self, attachments):
        for att in attachments:
            att_type = getattr(att, "type", None)
            payload = getattr(att, "payload", None)
            url = getattr(payload, "url", None) if payload is not None else None
            token = getattr(payload, "token", None) if payload is not None else None
            file_id = url or token or self._bot.synthetic_file_id()
            if att_type == "image":
                self.photo.append(PhotoSize(file_id=str(file_id)))
            elif att_type == "video":
                self.video = Video(file_id=str(file_id))
            elif att_type == "file":
                file_name = getattr(att, "filename", None)
                file_size = getattr(att, "size", 0) or 0
                mime = None
                self.document = Document(
                    file_id=str(file_id),
                    file_name=file_name,
                    file_size=int(file_size),
                    mime_type=mime,
                )

    async def answer(self, text: str | None = None, reply_markup=None, parse_mode=None, attachments=None):
        return await self._bot.send_message(
            chat_id=self.chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            attachments=attachments,
        )

    async def answer_photo(self, photo, caption: str | None = None, reply_markup=None, parse_mode=None):
        return await self._bot.send_photo(
            chat_id=self.chat.id,
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    async def answer_video(self, video, caption: str | None = None, reply_markup=None, parse_mode=None):
        return await self._bot.send_video(
            chat_id=self.chat.id,
            video=video,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    async def answer_document(self, document, caption: str | None = None, reply_markup=None, parse_mode=None):
        return await self._bot.send_document(
            chat_id=self.chat.id,
            document=document,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    async def edit_text(self, text: str, reply_markup=None, parse_mode=None):
        return await self._bot.edit_message_text(
            chat_id=self.chat.id,
            message_id=self.message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    async def edit_reply_markup(self, reply_markup=None):
        return await self._bot.edit_message_text(
            chat_id=self.chat.id,
            message_id=self.message_id,
            text=self.text or "",
            reply_markup=reply_markup,
        )

    async def delete(self):
        return await self._bot.delete_message(chat_id=self.chat.id, message_id=self.message_id)


class CallbackQuery:
    def __init__(self, bot, callback_event):
        self._bot = bot
        self._event = callback_event
        self.data = getattr(getattr(callback_event, "callback", None), "payload", None)
        self.message = Message(bot, callback_event.message, callback_event=callback_event)

        user = getattr(getattr(callback_event, "callback", None), "user", None)
        user_id = getattr(user, "user_id", 0) if user else 0
        username = getattr(user, "username", None) if user else None
        full_name = getattr(user, "full_name", "") if user else ""
        self.from_user = User(id=int(user_id), username=username, full_name=full_name)

    async def answer(self, text: str | None = None, show_alert: bool = False):
        # Send only the notification without a message payload.
        # The old approach called event.answer() which reconstructs the
        # original attachments (buttons) and overwrites any edit_message_text
        # changes, causing buttons to revert to their previous state.
        try:
            callback_obj = getattr(self._event, "callback", None)
            callback_id = getattr(callback_obj, "callback_id", None) if callback_obj else None
            if callback_id:
                # MAX API requires at least `notification` or `message`.
                # If text is None or empty string (empty call.answer()), 
                # JUST SKIP — no need to send anything to the server.
                if not text:
                    return None
                return await self._bot._max_bot.send_callback(
                    callback_id=callback_id,
                    message=None,
                    notification=text,
                )
        except Exception:
            return None
        return None


__all__ = [
    "Message",
    "CallbackQuery",
    "MessageEntity",
    "InlineKeyboardButton",
    "InlineKeyboardMarkup",
    "KeyboardButton",
    "ReplyKeyboardMarkup",
    "InputMediaPhoto",
    "InputMediaVideo",
    "FSInputFile",
    "InputFile",
    "BufferedInputFile",
]
