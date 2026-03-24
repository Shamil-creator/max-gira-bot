from __future__ import annotations

from typing import List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class InlineKeyboardBuilder:
    def __init__(self):
        self._buttons: List[InlineKeyboardButton] = []
        self._rows: List[List[InlineKeyboardButton]] = []

    def button(self, text: str, callback_data: str | None = None, style: str | None = None):
        self._buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data, style=style))

    def row(self, *buttons: InlineKeyboardButton):
        if buttons:
            self._rows.append(list(buttons))

    def add(self, button: InlineKeyboardButton):
        self._buttons.append(button)

    def adjust(self, *sizes: int):
        if not self._buttons:
            return
        idx = 0
        size_idx = 0
        while idx < len(self._buttons):
            size = sizes[size_idx] if size_idx < len(sizes) else sizes[-1]
            self._rows.append(self._buttons[idx : idx + size])
            idx += size
            size_idx += 1
        self._buttons = []

    def as_markup(self) -> InlineKeyboardMarkup:
        if self._buttons and not self._rows:
            self._rows = [[btn] for btn in self._buttons]
            self._buttons = []
        return InlineKeyboardMarkup(inline_keyboard=self._rows or [[]])
