import asyncio
import logging
import sys

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
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def get_data(query: str, *params):
    try:
        conn = await asyncpg.connect(config.db_connection)
        result = await conn.fetch(query, *params)
        await conn.close()
        return result
    except Exception as e:
        logger.error("DB error: %s", e)
        return None


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


async def setup_scheduler():
    ids_record = await get_data("SELECT user_id FROM users")
    if not ids_record:
        return

    list_ids = [ids["user_id"] for ids in ids_record]
    logger.info("Scheduler setup for users: %s", list_ids)

    for id_us in list_ids:
        scheduler.add_job(
            get_message_every_month,
            trigger=CronTrigger(day=20, hour=0, minute=12, timezone="Europe/Moscow"),
            args=[id_us],
            id=f"monthly_payment_msg_{id_us}",
            replace_existing=True,
        )
        scheduler.add_job(
            get_mr_message_every_month,
            trigger=CronTrigger(day=20, hour=0, minute=13, timezone="Europe/Moscow"),
            args=[id_us],
            id=f"monthly_mr_msg_{id_us}",
            replace_existing=True,
        )
        scheduler.add_job(
            get_invoice_msg_every_month,
            trigger=CronTrigger(day=20, hour=0, minute=14, timezone="Europe/Moscow"),
            args=[id_us],
            id=f"monthly_invoice_msg_{id_us}",
            replace_existing=True,
        )
        scheduler.add_job(
            get_act_of_payment,
            trigger=CronTrigger(day=20, hour=0, minute=15, timezone="Europe/Moscow"),
            args=[id_us],
            id=f"monthly_act_msg_{id_us}",
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
