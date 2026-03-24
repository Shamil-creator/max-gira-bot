from pathlib import Path
import asyncio
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aiogram import Bot
from handlers.images_cache import ImageCache
from maxapi.enums.attachment import AttachmentType


def _fake_send_message_response(mid: str = "m1", url: str | None = None):
    attachments = []
    if url:
        attachments = [SimpleNamespace(payload=SimpleNamespace(url=url))]
    return SimpleNamespace(
        message=SimpleNamespace(
            body=SimpleNamespace(
                mid=mid,
                attachments=attachments,
            )
        )
    )


def test_send_photo_supports_http_url_reference():
    bot = Bot(token="test-token")
    captured = {}

    async def fake_send_message(**kwargs):
        captured.update(kwargs)
        return _fake_send_message_response(mid="photo-mid")

    bot._max_bot.send_message = fake_send_message

    photo_url = "https://example.com/image.jpg"
    sent = asyncio.run(bot.send_photo(chat_id=1, photo=photo_url, caption="caption"))

    assert captured["chat_id"] == 1
    assert captured["text"] == "caption"
    assert captured["attachments"][0].type == AttachmentType.IMAGE
    assert captured["attachments"][0].payload.url == photo_url
    assert sent.photo and sent.photo[0].file_id == photo_url


def test_send_video_supports_http_url_reference():
    bot = Bot(token="test-token")
    captured = {}

    async def fake_send_message(**kwargs):
        captured.update(kwargs)
        return _fake_send_message_response(mid="video-mid")

    bot._max_bot.send_message = fake_send_message

    video_url = "https://example.com/video.mp4"
    sent = asyncio.run(bot.send_video(chat_id=1, video=video_url, caption="caption"))

    assert captured["chat_id"] == 1
    assert captured["text"] == "caption"
    assert captured["attachments"][0].type == AttachmentType.VIDEO
    assert captured["attachments"][0].payload.url == video_url
    assert sent.video and sent.video.file_id == video_url


def test_image_cache_uses_local_files_for_telegram_file_ids():
    cache = ImageCache()
    cache.water_id = "AgACAgIAAyEGAATHoDu-AAIURGmtQrqNon9l_gzbMG7uf4JZNBMUAALMGWsbeKxpSVpO8Si09pn_AQADAgADeQADOgQ"
    cache.electricity_id = "AgACAgIAAyEGAATHoDu-AAIURWmtQr81oIoTr1gETppAGsftB0jpAALNGWsbeKxpSX1hymJVgGv0AQADAgADeAADOgQ"

    assert cache.get_water() == "images/new_water.png"
    assert cache.get_electricity() == "images/electricity.png"


def test_image_cache_quick_validate_accepts_only_http_refs():
    cache = ImageCache()
    cache.water_id = "AgACbad"
    cache.electricity_id = "AgACbad2"
    assert asyncio.run(cache._quick_validate()) is False

    cache.water_id = "https://cdn.example.com/water.png"
    cache.electricity_id = "https://cdn.example.com/electricity.png"
    assert asyncio.run(cache._quick_validate()) is True
