from __future__ import annotations

import json
from typing import Any

import asyncpg


class PostgresDraftStore:
    """Redis-like async interface backed by PostgreSQL for bot drafts."""

    def __init__(self, dsn: str):
        self._dsn = dsn

    async def init_schema(self):
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_drafts (
                    draft_key TEXT PRIMARY KEY,
                    scalar_value TEXT NULL,
                    list_value JSONB NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bot_drafts_updated_at
                ON bot_drafts(updated_at)
                """
            )
        finally:
            await conn.close()

    async def _fetchrow(self, key: str):
        conn = await asyncpg.connect(self._dsn)
        try:
            return await conn.fetchrow(
                "SELECT scalar_value, list_value FROM bot_drafts WHERE draft_key = $1",
                key,
            )
        finally:
            await conn.close()

    async def _upsert(self, key: str, scalar_value: str | None, list_value: list[str] | None):
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                """
                INSERT INTO bot_drafts(draft_key, scalar_value, list_value, updated_at)
                VALUES($1, $2, $3::jsonb, NOW())
                ON CONFLICT (draft_key)
                DO UPDATE SET scalar_value = EXCLUDED.scalar_value,
                              list_value = EXCLUDED.list_value,
                              updated_at = NOW()
                """,
                key,
                scalar_value,
                json.dumps(list_value) if list_value is not None else None,
            )
        finally:
            await conn.close()

    async def _load_list(self, key: str) -> list[str]:
        row = await self._fetchrow(key)
        if not row:
            return []
        value = row["list_value"]
        if not value:
            return []
        if isinstance(value, str):
            try:
                data = json.loads(value)
            except Exception:
                return []
            return [str(x) for x in data]
        return [str(x) for x in value]

    async def set(self, key: str, value: Any):
        await self._upsert(key, str(value), None)
        return True

    async def get(self, key: str):
        row = await self._fetchrow(key)
        if not row:
            return None
        return row["scalar_value"]

    async def delete(self, *keys: str):
        if not keys:
            return 0
        conn = await asyncpg.connect(self._dsn)
        try:
            result = await conn.execute(
                "DELETE FROM bot_drafts WHERE draft_key = ANY($1::text[])",
                list(keys),
            )
            return int(result.split()[-1])
        finally:
            await conn.close()

    async def llen(self, key: str):
        items = await self._load_list(key)
        return len(items)

    async def lpush(self, key: str, *values: Any):
        items = await self._load_list(key)
        head = [str(v) for v in values]
        items = head + items
        await self._upsert(key, None, items)
        return len(items)

    async def rpush(self, key: str, *values: Any):
        items = await self._load_list(key)
        items.extend(str(v) for v in values)
        await self._upsert(key, None, items)
        return len(items)

    async def lrange(self, key: str, start: int, end: int):
        items = await self._load_list(key)
        if not items:
            return []

        n = len(items)
        if start < 0:
            start = max(0, n + start)
        if end < 0:
            end = n + end
        end = min(end, n - 1)
        if start > end or start >= n:
            return []
        return items[start : end + 1]

    async def lset(self, key: str, index: int, value: Any):
        items = await self._load_list(key)
        if index < 0 or index >= len(items):
            raise IndexError("list assignment index out of range")
        items[index] = str(value)
        await self._upsert(key, None, items)
        return True

    async def lrem(self, key: str, count: int, value: Any):
        target = str(value)
        items = await self._load_list(key)
        removed = 0

        if count == 0:
            new_items = []
            for item in items:
                if item == target:
                    removed += 1
                else:
                    new_items.append(item)
        elif count > 0:
            new_items = []
            for item in items:
                if item == target and removed < count:
                    removed += 1
                    continue
                new_items.append(item)
        else:
            remaining = -count
            rev = list(reversed(items))
            new_rev = []
            for item in rev:
                if item == target and removed < remaining:
                    removed += 1
                    continue
                new_rev.append(item)
            new_items = list(reversed(new_rev))

        await self._upsert(key, None, new_items)
        return removed
