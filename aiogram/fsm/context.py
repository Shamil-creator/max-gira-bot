from __future__ import annotations

from typing import Any


class FSMContext:
    """Thin wrapper over maxapi MemoryContext-like object."""

    def __init__(self, memory_context):
        self._ctx = memory_context

    async def get_data(self) -> dict[str, Any]:
        return await self._ctx.get_data()

    async def set_data(self, data: dict[str, Any]):
        await self._ctx.set_data(data)

    async def update_data(self, data: dict[str, Any] | None = None, **kwargs):
        if data:
            kwargs.update(data)
        await self._ctx.update_data(**kwargs)

    async def set_state(self, state=None):
        await self._ctx.set_state(state)

    async def get_state(self):
        return await self._ctx.get_state()

    async def clear(self):
        await self._ctx.clear()
