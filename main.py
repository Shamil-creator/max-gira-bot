import asyncio
import logging
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from aiogram import Bot, Dispatcher

# Handlers import `from main import ...` in many places.
# When started as `python main.py`, module name is `__main__`, so without this alias
# Python may load a second module instance named `main`.
sys.modules.setdefault("main", sys.modules[__name__])

from handlers.add_new_electricity_meter_readings import add_new_el_mr_router
from handlers.add_new_water_meter_readings import add_new_mr_router
from handlers.admin_group import admin_router
from handlers.admin_meter_handlers import admin_meter_router
from handlers.check_payment_status import (
    get_act_ku_payment_every_month,
    get_act_of_payment,
    get_invoice_msg_every_month,
    get_message_every_month,
    get_mr_message_every_month,
    payment_router,
    spam_message_every_hour,
)
from handlers.config import config
from handlers.images_cache import image_cache
from handlers.meter_readings import meter_readings_router
from handlers.notifications import notifications_router
from handlers.reg_user import reg_router
from handlers.repair_work import repair_work_router
from handlers.run import run_router
from handlers.technical_request import technical_request_router
from services.draft_store import PostgresDraftStore

logging.getLogger("yadisk").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.max_bot_token.get_secret_value().strip("'\""))
dp = Dispatcher(bot=bot)
redis = PostgresDraftStore(config.db_connection)

CHAT_ID = int(config.chanel_id.get_secret_value().strip("'\""))
SCHEDULER_TZ = ZoneInfo("Europe/Moscow")
scheduler = AsyncIOScheduler(timezone=SCHEDULER_TZ)


async def get_data(query: str, *params):
    conn = None
    try:
        conn = await asyncpg.connect(config.db_connection)
        return await conn.fetch(query, *params)
    except Exception as e:
        logger.error("DB error: %s", e)
        return None
    finally:
        if conn:
            await conn.close()


async def spam_scheduler(us_id):
    job_id = f"minute_spam_{us_id}"
    scheduler.add_job(
        spam_message_every_hour,
        trigger=CronTrigger(hour="*", minute="*"),
        args=[us_id],
        id=job_id,
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()
    logger.info("Spam scheduler started for user %s", us_id)


async def reset_monthly_counter_status():
    """Сбрасывает статусы подачи показаний для всех пользователей в начале месяца."""
    from aiogram.fsm.storage.base import StorageKey

    ids_record = await get_data("SELECT user_id FROM users")
    if not ids_record:
        return
    for record in ids_record:
        try:
            user_id = int(record["user_id"])
            key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
            data = await dp.fsm.storage.get_data(key=key)
            data["counter_status_hw"] = False
            data["counter_status_cw"] = False
            data["counter_status_el"] = False
            data["payment_confirmed"] = False
            await dp.fsm.storage.set_data(key=key, data=data)
        except Exception as e:
            logger.warning("Не удалось сбросить счётчики для user_id=%s: %s", record["user_id"], e)
    logger.info("Статусы показаний сброшены для всех пользователей")


async def setup_scheduler():
    ids_record = await get_data("SELECT user_id FROM users")
    if not ids_record:
        return

    list_ids = [ids["user_id"] for ids in ids_record]
    logger.info("Scheduler setup for users: %s", list_ids)

    # Сброс статусов показаний 1-го числа каждого месяца в 00:01
    scheduler.add_job(
        reset_monthly_counter_status,
        trigger=CronTrigger(day=1, hour=0, minute=1, timezone="Europe/Moscow"),
        id="monthly_counter_reset",
        replace_existing=True,
    )

    for i, id_us in enumerate(list_ids):
        scheduler.add_job(
            get_message_every_month,
            trigger=CronTrigger(day="5-28", hour=12, minute=i * 2, timezone="Europe/Moscow"),
            args=[id_us],
            id=f"monthly_payment_msg_{id_us}",
            replace_existing=True,
        )
        scheduler.add_job(
            get_mr_message_every_month,
            trigger=CronTrigger(day="10-15", hour=10, minute=i * 2, timezone="Europe/Moscow"),
            args=[id_us],
            id=f"monthly_mr_msg_{id_us}",
            replace_existing=True,
        )
        scheduler.add_job(
            get_invoice_msg_every_month,
            trigger=CronTrigger(day="28-31", hour=3, minute=21 + i * 2, timezone="Europe/Moscow"),
            args=[id_us],
            id=f"monthly_invoice_msg_{id_us}",
            replace_existing=True,
        )
        scheduler.add_job(
            get_act_of_payment,
            trigger=CronTrigger(day="28-31", hour=3, minute=22 + i * 2, timezone="Europe/Moscow"),
            args=[id_us],
            id=f"monthly_act_msg_{id_us}",
            replace_existing=True,
        )
        scheduler.add_job(
            get_act_ku_payment_every_month,
            trigger=CronTrigger(day="28-31", hour=3, minute=23 + i * 2, timezone="Europe/Moscow"),
            args=[id_us],
            id=f"monthly_act_ku_msg_{id_us}",
            replace_existing=True,
        )

    if not scheduler.running:
        scheduler.start()


async def on_startup():
    logger.info("Initializing Postgres drafts storage...")
    await redis.init_schema()

    logger.info("Initializing image cache...")
    await image_cache.initialize(bot, upload_chat_id=CHAT_ID)

    logger.info("Starting scheduler...")
    await setup_scheduler()


async def main():
    dp.include_router(admin_router)
    dp.include_router(payment_router)
    dp.include_router(add_new_el_mr_router)
    dp.include_router(add_new_mr_router)
    dp.include_router(run_router)
    dp.include_router(technical_request_router)
    dp.include_router(reg_router)
    dp.include_router(repair_work_router)
    dp.include_router(meter_readings_router)
    dp.include_router(notifications_router)
    dp.include_router(admin_meter_router)
    dp.startup.register(on_startup)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("MAX bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
