from __future__ import annotations

from typing import Any

CATEGORY_PREFIX = {
    "PAYMENT": "[ОПЛАТА]",
    "TECH": "[ТЕХЗАЯВКА]",
    "TERMINATION": "[РАСТОРЖЕНИЕ]",
    "REPAIR": "[РЕМОНТ]",
    "DOCS": "[ДОКУМЕНТЫ]",
    "ADMIN": "[АДМИН]",
}


def _normalize_category(category: str) -> str:
    return (category or "ADMIN").strip().upper()


def format_admin_text(category: str, text: str) -> str:
    normalized = _normalize_category(category)
    prefix = CATEGORY_PREFIX.get(normalized, CATEGORY_PREFIX["ADMIN"])
    body = text or ""
    return f"{prefix} {body}"


async def send_to_admin_chat(
    bot,
    chat_id: int,
    category: str,
    text: str,
    reply_markup: Any = None,
    parse_mode: str | None = None,
):
    return await bot.send_message(
        chat_id=chat_id,
        text=format_admin_text(category, text),
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )
