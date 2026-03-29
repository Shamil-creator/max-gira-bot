from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StorageKey:
    bot_id: Any
    chat_id: int
    user_id: int


class BaseStorage:
    """Minimal in-memory FSM storage accessible by StorageKey."""

    def __init__(self):
        self._data: dict[tuple[int, int], dict[str, Any]] = {}

    def _key(self, key: StorageKey) -> tuple[int, int]:
        return (int(key.chat_id), int(key.user_id))

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        return self._data.get(self._key(key), {})

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        self._data[self._key(key)] = data
