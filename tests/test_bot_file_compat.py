from pathlib import Path
import asyncio
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aiogram import Bot


def test_get_file_returns_file_path_wrapper():
    bot = Bot(token="test-token")
    wrapped = asyncio.run(bot.get_file("max:file:123"))
    assert wrapped.file_path == "max:file:123"


def test_download_file_copies_local_file(tmp_path):
    bot = Bot(token="test-token")
    src = tmp_path / "src.txt"
    dst = tmp_path / "nested" / "dst.txt"
    src.write_text("hello", encoding="utf-8")

    result = asyncio.run(bot.download_file(str(src), str(dst)))

    assert result == str(dst)
    assert dst.read_text(encoding="utf-8") == "hello"


def test_download_file_raises_for_unknown_reference(tmp_path):
    import pytest

    bot = Bot(token="test-token")
    dst = tmp_path / "dst.txt"

    with pytest.raises(FileNotFoundError):
        asyncio.run(bot.download_file("max:file:unknown", str(dst)))
