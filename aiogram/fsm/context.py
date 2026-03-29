from __future__ import annotations

from typing import Any


class FSMContext:
    """Thin wrapper over maxapi MemoryContext-like object."""

    def __init__(self, memory_context, global_storage=None, storage_key=None):
        self._ctx = memory_context
        self._global_storage = global_storage
        self._storage_key = storage_key

    async def _sync_to_global(self, data: dict[str, Any]):
        if self._global_storage is not None and self._storage_key is not None:
            await self._global_storage.set_data(key=self._storage_key, data=data)

    async def get_data(self) -> dict[str, Any]:
        return await self._ctx.get_data()

    async def set_data(self, data: dict[str, Any]):
        await self._ctx.set_data(data)
        await self._sync_to_global(data)

    async def update_data(self, data: dict[str, Any] | None = None, **kwargs):
        if data:
            kwargs.update(data)
        await self._ctx.update_data(**kwargs)
        current = await self._ctx.get_data()
        await self._sync_to_global(current)

    async def set_state(self, state=None):
        await self._ctx.set_state(state)

    async def get_state(self):
        return await self._ctx.get_state()

    async def clear(self):
        await self._ctx.clear()
        await self._sync_to_global({})
