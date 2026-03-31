import calendar
from datetime import date, datetime
import tempfile
from docx import Document
from aiogram import Bot, types, Router
from aiogram.types import Message, CallbackQuery,MessageEntity
from aiogram.filters.command import Command
import os
import asyncio
import logging
from aiogram import F
from aiogram.types.input_file import FSInputFile
import asyncpg
from handlers.config import config
from aiogram.fsm.state import State
from aiogram.fsm.context import FSMContext
import psycopg2
from aiogram.types import InputMediaPhoto, InputMediaVideo, FSInputFile
import schedule

from handlers.create_layout import create_invoice_for_payment_for_user, create_layoat_for_user
from handlers.run import get_form_of_doing_info_business, get_info_business, get_readings_info

payment_router = Router()

async def get_data(query: str, *params):
    """Основной метод работы с БД"""
    conn = None
    try:
        conn = await asyncpg.connect(config.db_connection)
        return await conn.fetch(query, *params)
    except Exception as e:
        logging.error(f"Ошибка БД: {e}")
        return None
    finally:
        if conn:
            await conn.close()

async def new_data_insert(query: str, *params):
    conn = None
    try:
        conn = await asyncpg.connect(config.db_connection)
        return await conn.execute(query, *params)
    except Exception as e:
        print(f"Ошибка: {e}")
        return None
    finally:
        if conn:
            await conn.close()


async def stop_spam_scheduler(us_id: int):
    from main import scheduler,logger
    job_id = f'minute_spam_{us_id}'
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"⛔ Остановлен спам для пользователя {us_id}")
        return True
    return False

def stoped_keyboard(id):
    cb = f'stop_spam_cb:{id}'
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text='Завершить спам', callback_data=cb)]
        ]
    )
    return keyboard

def ask_payment_tenant_keyboard(id):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="✅ Оплатил", 
                callback_data=f"tenant_yes_reaction_cb:{id}"
            ),
            types.InlineKeyboardButton(
                text="❌ Не оплатил", 
                callback_data=f"tenant_no_reaction_cb:{id}"
            )
        ]
    ])
    return keyboard

def ask_payment_landlord_keyboard(id):
    buttons = [
        [types.InlineKeyboardButton(text='✅ Оплатил', callback_data=f'landlord_yes_reaction_cb:{id}'), types.InlineKeyboardButton(text='❌ Не оплатил', callback_data=f'landlord_no_reaction_cb:{id}')]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons, resize_keyboard=True)
    return keyboard

async def spam_message_every_hour(id):
    from main import bot
    await bot.send_message(chat_id=id, text='Здравствуйте! Напоминаем вам о необходимости оплаты ежемесячного арендного платежа.')

async def get_message_every_month(id):
    from main import bot, dp
    from aiogram.fsm.storage.base import StorageKey

    try:
        key = StorageKey(bot_id=bot.id, chat_id=int(id), user_id=int(id))
        data = await dp.fsm.storage.get_data(key=key)
    except Exception:
        data = {}

    if data.get('payment_confirmed'):
        return

    await bot.send_message(chat_id=id, text='Здравствуйте! Напоминаем вам о необходимости оплаты ежемесячного арендного платежа. Укажите вы уже внесли платёж?', reply_markup=ask_payment_tenant_keyboard(id))

def submit_readings_keyboard():
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text='📝 Подать показания', callback_data='submit_readings_from_reminder')]
    ])
    return keyboard

async def get_mr_message_every_month(id):
    from main import bot, dp
    from aiogram.fsm.storage.base import StorageKey

    try:
        key = StorageKey(bot_id=bot.id, chat_id=int(id), user_id=int(id))
        data = await dp.fsm.storage.get_data(key=key)
    except Exception:
        data = {}

    try:
        meters = await get_data(
            'SELECT ur.number_counter, tc.name FROM us_readings ur '
            'JOIN type_counter tc ON ur.counter_type_id = tc.id '
            'WHERE ur.business_id = (SELECT id_business FROM users WHERE User_Id = $1)',
            str(id)
        )
    except Exception:
        meters = None
    if not meters:
        return

    has_water = any(m['name'] in ('Холодная вода', 'Горячая вода') for m in meters)
    has_electricity = any(m['name'] == 'Электричество' for m in meters)

    water_done = data.get('counter_status_hw') and data.get('counter_status_cw')
    electricity_done = data.get('counter_status_el')

    if (not has_water or water_done) and (not has_electricity or electricity_done):
        return

    meter_lines = []
    for m in meters:
        type_name = m['name']
        number = m['number_counter']
        if type_name == 'Холодная вода':
            meter_lines.append(f"❄️ ХВС: №{number}")
        elif type_name == 'Горячая вода':
            meter_lines.append(f"🔥 ГВС: №{number}")
        elif type_name == 'Электричество':
            meter_lines.append(f"⚡ Электричество: №{number}")
    meters_text = "\n".join(meter_lines)
    text = (
        f"Здравствуйте! Необходимо внести показания счетчиков до 15 числа текущего месяца\n\n"
        f"Ваши счетчики:\n{meters_text}"
    )
    await bot.send_message(chat_id=id, text=text, reply_markup=submit_readings_keyboard())
    
async def build_rent_invoice(id):
    """Generate rent invoice xlsx. Returns (path, filename, caption) or None."""
    today = datetime.now()
    if today.month == 12:
        target_date = datetime(today.year + 1, 1, 1)
    else:
        target_date = datetime(today.year, today.month + 1, 1)

    records_list = await get_info_business(id)
    fod_name = await get_form_of_doing_info_business(id)
    if not records_list:
        return None
    rec = records_list[0]
    name = rec['name_company']
    agreement = rec['agreement']
    bid = rec['bid']
    square = rec['square']
    number_act = rec['number_act']
    director_title = rec.get('director_title')
    number_act = int(number_act) + 1 if number_act is not None else 1
    full_name = f'''{fod_name} "{name}"'''
    full_name_tenant = f"{rec['surname']} {rec['first_name']} {rec['patronymic']}"

    xlsx_path = await create_invoice_for_payment_for_user(
        act_number=number_act,
        name_company='ООО "ГИРА"',
        name_company_tenant=full_name,
        agreement=agreement,
        price=bid,
        square=square,
        full_name_tenant=full_name_tenant,
        tenant_director_title=director_title or 'Директор',
        target_date=target_date,
    )
    nice_filename = f"Счет на оплату аренды {target_date.strftime('%m.%Y')}.xlsx"
    caption = 'Здравствуйте! Ваш счет за текущий месяц'
    return xlsx_path, nice_filename, caption


async def get_invoice_msg_every_month(id, force=False):
    from main import bot
    try:
        today = datetime.now()
        if not force:
            last_day = calendar.monthrange(today.year, today.month)[1]
            if today.day != last_day:
                return

        result = await build_rent_invoice(id)
        if result is None:
            logging.warning("[invoice] Нет данных о компании для user_id=%s — пропуск", id)
            return
        xlsx_path, nice_filename, caption = result

        records_list = await get_info_business(id)
        rec = records_list[0]
        name = rec['name_company']
        number_act = int(rec['number_act']) + 1 if rec['number_act'] is not None else 1

        document = FSInputFile(xlsx_path, filename=nice_filename)
        number_act_to_save = number_act + 1
        await new_data_insert('UPDATE bussines SET number_act = $1 WHERE name_company = $2', number_act_to_save, name)
        sent_message = await bot.send_document(chat_id=id, document=document, caption=caption)
        logging.info("[invoice] Счёт отправлен user_id=%s", id)
        today_date = date.today()
        file_id = sent_message.document.file_id
        records = await get_data('SELECT id_business FROM users WHERE User_Id = $1', str(id))
        id_business = records[0]['id_business']
        await new_data_insert('INSERT INTO business_documents(id_business, file_id, date_added, file_name) VALUES ($1, $2, $3, $4)', id_business, file_id, today_date, nice_filename)
    except Exception as e:
        logging.error("[invoice] Ошибка при отправке счёта user_id=%s: %s", id, e, exc_info=True)

async def build_rent_act(id):
    """Generate rent act xlsx. Returns (path, filename, caption) or None."""
    today = datetime.now()
    records_list = await get_info_business(id)
    fod_name = await get_form_of_doing_info_business(id)
    if not records_list:
        return None

    name = square = agreement = bid = surname = first_name = patronymic = number_act = director_title = None
    for rec in records_list:
        name = rec['name_company']
        square = rec['square']
        agreement = rec['agreement']
        bid = rec['bid']
        surname = rec['surname']
        first_name = rec['first_name']
        patronymic = rec['patronymic']
        number_act = rec['number_act']
        director_title = rec.get('director_title')

    full_name_tenant = f'{surname} {first_name} {patronymic}'
    tenant_with_form = f'''{fod_name} "{name}"'''

    last_day = calendar.monthrange(today.year, today.month)[1]
    end_of_month = today.replace(day=last_day)
    end_str = end_of_month.strftime("%d.%m.%Y")

    xlsx_path = await create_layoat_for_user('ООО "ГИРА"', tenant_with_form, end_str, bid, square, agreement, full_name_tenant, number_act, tenant_director_title=director_title or 'Директор')
    nice_filename = f"Акт за аренду №{number_act} от {end_str}.xlsx"
    caption = 'Здравствуйте! Ваш Акт за аренду за текущий месяц'
    return xlsx_path, nice_filename, caption


async def get_act_of_payment(id, force=False):
    from main import bot
    try:
        today = datetime.now()
        if not force:
            last_day = calendar.monthrange(today.year, today.month)[1]
            if today.day != last_day:
                return

        result = await build_rent_act(id)
        if result is None:
            logging.warning("[act] Нет данных о компании для user_id=%s — пропуск", id)
            return
        xlsx_path, nice_filename, caption = result

        records_list = await get_info_business(id)
        rec = records_list[0]
        name, square = rec['name_company'], rec['square']
        number_act_to_save = (int(rec['number_act']) if rec['number_act'] is not None else 0) + 1

        document = FSInputFile(xlsx_path, filename=nice_filename)
        await new_data_insert('UPDATE bussines SET number_act = $1 WHERE square = $2 AND name_company = $3', number_act_to_save, square, name)
        sent_message = await bot.send_document(chat_id=id, document=document, caption=caption)
        logging.info("[act] Акт отправлен user_id=%s", id)

        today_date = date.today()
        file_id = sent_message.document.file_id
        records = await get_data('SELECT id_business FROM users WHERE User_Id = $1', str(id))
        id_business = records[0]['id_business']
        await new_data_insert('INSERT INTO business_documents(id_business, file_id, date_added, file_name) VALUES ($1, $2, $3, $4)', id_business, file_id, today_date, nice_filename)
    except Exception as e:
        logging.error("[act] Ошибка при отправке акта user_id=%s: %s", id, e, exc_info=True)


async def build_ku_act_payment(id):
    """Generate KU act xlsx. Returns (path, filename, caption) or None."""
    today = datetime.now()
    records_list = await get_info_business(id)
    fod_name = await get_form_of_doing_info_business(id)
    if not records_list:
        return None

    records = await get_data('SELECT id_business FROM users WHERE User_Id = $1', str(id))
    if not records or not records[0]['id_business']:
        return None
    id_business = records[0]['id_business']

    meters_check = await get_data(
        'SELECT COUNT(*) as cnt FROM us_readings WHERE business_id = $1',
        id_business
    )
    if not meters_check or meters_check[0]['cnt'] == 0:
        return None

    from handlers.excel_tg_test import compute_ku_total_from_excel
    ku_total = await compute_ku_total_from_excel(id)
    if ku_total is None or ku_total == 0:
        return None

    biz = records_list[0]
    agreement = biz.get('agreement', '')
    number_act_ku = biz.get('number_act_ku')
    ku_number = int(number_act_ku or 0) + 1
    full_name = f'''{fod_name} "{biz['name_company']}"'''
    full_name_tenant = f"{biz['surname']} {biz['first_name']} {biz['patronymic']}"

    last_day = calendar.monthrange(today.year, today.month)[1]
    start_period = today.replace(day=1).strftime("%d.%m.%Y")
    end_period = today.replace(day=last_day).strftime("%d.%m.%Y")

    from handlers.create_layout import create_act_payment_ku_for_user
    xlsx_path = await create_act_payment_ku_for_user(
        act_number=ku_number,
        name_company='ООО "ГИРА"',
        name_company_tenant=full_name,
        agreement=agreement,
        price=ku_total,
        square=biz.get('square', 0),
        start_period=start_period,
        end_period=end_period,
        full_name_tenant=full_name_tenant,
        tenant_director_title=biz.get('director_title') or 'Директор',
        target_date=today,
    )

    months_ru = {
        1: 'январь', 2: 'февраль', 3: 'март', 4: 'апрель',
        5: 'май', 6: 'июнь', 7: 'июль', 8: 'август',
        9: 'сентябрь', 10: 'октябрь', 11: 'ноябрь', 12: 'декабрь'
    }
    month_name = months_ru[today.month]
    nice_filename = f"Акт №{ku_number} КУ {month_name} {today.year}.xlsx"
    caption = 'Здравствуйте! Ваш акт оплаты КУ за текущий месяц'
    return xlsx_path, nice_filename, caption


async def build_ku_invoice(id):
    """Generate KU invoice (Счет на оплату КУ) xlsx. Returns (path, filename, caption) or None."""
    today = datetime.now()
    records_list = await get_info_business(id)
    fod_name = await get_form_of_doing_info_business(id)
    if not records_list:
        return None

    records = await get_data('SELECT id_business FROM users WHERE User_Id = $1', str(id))
    if not records or not records[0]['id_business']:
        return None
    id_business = records[0]['id_business']

    meters_check = await get_data(
        'SELECT COUNT(*) as cnt FROM us_readings WHERE business_id = $1',
        id_business
    )
    if not meters_check or meters_check[0]['cnt'] == 0:
        return None

    from handlers.excel_tg_test import compute_ku_total_from_excel
    ku_total = await compute_ku_total_from_excel(id)
    if ku_total is None or ku_total == 0:
        return None

    biz = records_list[0]
    agreement = biz.get('agreement', '')
    number_act_ku = biz.get('number_act_ku')
    ku_number = int(number_act_ku or 0) + 1
    full_name = f'''{fod_name} "{biz['name_company']}"'''
    full_name_tenant = f"{biz['surname']} {biz['first_name']} {biz['patronymic']}"

    last_day = calendar.monthrange(today.year, today.month)[1]
    start_period = today.replace(day=1).strftime("%d.%m.%Y")
    end_period = today.replace(day=last_day).strftime("%d.%m.%Y")

    from handlers.create_layout import create_invoice_for_ku_for_user
    xlsx_path = await create_invoice_for_ku_for_user(
        act_number=ku_number,
        name_company='ООО "ГИРА"',
        name_company_tenant=full_name,
        agreement=agreement,
        price=ku_total,
        square=biz.get('square', 0),
        start_period=start_period,
        end_period=end_period,
        full_name_tenant=full_name_tenant,
        tenant_director_title=biz.get('director_title') or 'Директор',
        target_date=today,
    )

    months_ru = {
        1: 'январь', 2: 'февраль', 3: 'март', 4: 'апрель',
        5: 'май', 6: 'июнь', 7: 'июль', 8: 'август',
        9: 'сентябрь', 10: 'октябрь', 11: 'ноябрь', 12: 'декабрь'
    }
    month_name = months_ru[today.month]
    nice_filename = f"Счет на оплату КУ {month_name} {today.year}.xlsx"
    caption = 'Здравствуйте! Ваш счёт на оплату КУ за текущий месяц'
    return xlsx_path, nice_filename, caption


async def get_ku_invoice_every_month(id, force=False):
    from main import bot
    try:
        today = datetime.now()
        if not force:
            last_day = calendar.monthrange(today.year, today.month)[1]
            if today.day != last_day:
                return

        result = await build_ku_invoice(id)
        if result is None:
            logging.warning("[invoice_ku] Нет данных / счётчиков / суммы КУ для user_id=%s — пропуск", id)
            return
        xlsx_path, nice_filename, caption = result

        document = FSInputFile(xlsx_path, filename=nice_filename)
        sent_message = await bot.send_document(
            chat_id=id, document=document, caption=caption
        )
        logging.info("[invoice_ku] Счёт КУ отправлен user_id=%s", id)

        records = await get_data('SELECT id_business FROM users WHERE User_Id = $1', str(id))
        id_business = records[0]['id_business']

        today_date = date.today()
        file_id = sent_message.document.file_id
        await new_data_insert(
            'INSERT INTO business_documents(id_business, file_id, date_added, file_name) VALUES ($1, $2, $3, $4)',
            id_business, file_id, today_date, nice_filename
        )
    except Exception as e:
        logging.error("[invoice_ku] Ошибка при отправке счёта КУ user_id=%s: %s", id, e, exc_info=True)

async def get_act_ku_payment_every_month(id, force=False):
    from main import bot
    try:
        today = datetime.now()
        if not force:
            last_day = calendar.monthrange(today.year, today.month)[1]
            if today.day != last_day:
                return

        result = await build_ku_act_payment(id)
        if result is None:
            logging.warning("[act_ku] Нет данных / счётчиков / суммы КУ для user_id=%s — пропуск", id)
            return
        xlsx_path, nice_filename, caption = result

        document = FSInputFile(xlsx_path, filename=nice_filename)
        sent_message = await bot.send_document(
            chat_id=id, document=document, caption=caption
        )
        logging.info("[act_ku] Акт КУ отправлен user_id=%s", id)

        records_list = await get_info_business(id)
        biz = records_list[0]
        ku_number = int(biz.get('number_act_ku') or 0) + 1
        records = await get_data('SELECT id_business FROM users WHERE User_Id = $1', str(id))
        id_business = records[0]['id_business']

        await new_data_insert(
            'UPDATE bussines SET number_act_ku = $1 WHERE id = $2',
            ku_number, id_business
        )

        today_date = date.today()
        file_id = sent_message.document.file_id
        await new_data_insert(
            'INSERT INTO business_documents(id_business, file_id, date_added, file_name) VALUES ($1, $2, $3, $4)',
            id_business, file_id, today_date, nice_filename
        )
    except Exception as e:
        logging.error("[act_ku] Ошибка при отправке акта КУ user_id=%s: %s", id, e, exc_info=True)


@payment_router.callback_query(F.data.startswith(('tenant_yes_reaction_cb','tenant_no_reaction_cb')))
async def callb(call: CallbackQuery, state: FSMContext):
    from main import bot,spam_scheduler
    from handlers.config import config
    from handlers.run import get_info_business
    id_chat = config.chanel_id.get_secret_value()
    data = call.data
    action, target_user_id_str = data.split(':')
    records_list = await get_info_business(target_user_id_str)
    current_date = datetime.now()
    date_text = f'{current_date.month}.{current_date.year}'
    if records_list:
        for list in records_list:
            toa_name = list['name']
            name = list['name_company']
    await call.message.delete()
    if 'tenant_yes_reaction_cb' in data :
        # функция сохранения в диск
        await bot.send_message(chat_id=id_chat, text=f'[ОПЛАТА] Платеж от арендатора:\nВид деятельности: {toa_name}\nНаименование: {name}\nДанный арендатор произвел оплату за текущий месяц - {date_text}?', reply_markup=ask_payment_landlord_keyboard(target_user_id_str))
    elif 'tenant_no_reaction_cb'in data:
        await spam_scheduler(target_user_id_str)

@payment_router.callback_query(F.data.startswith(('landlord_yes_reaction_cb', 'landlord_no_reaction_cb', 'stop_spam_cb')))
async def callb(call: CallbackQuery, state: FSMContext):
    from main import bot,spam_scheduler
    from handlers.config import config
    id_chat = config.chanel_id.get_secret_value()
    data = call.data
    action, us_id = data.split(':')
    await call.message.delete()
    if 'landlord_yes_reaction_cb' in data:
        # функция сохранения в диск
        await stop_spam_scheduler(us_id)
        from aiogram.fsm.storage.base import StorageKey
        from main import dp
        try:
            fsm_key = StorageKey(bot_id=bot.id, chat_id=int(us_id), user_id=int(us_id))
            fsm_data = await dp.fsm.storage.get_data(key=fsm_key)
            fsm_data['payment_confirmed'] = True
            await dp.fsm.storage.set_data(key=fsm_key, data=fsm_data)
        except Exception as e:
            logging.warning("Не удалось установить payment_confirmed для %s: %s", us_id, e)
        await bot.send_message(chat_id=us_id,text='Благодарим вас за оплату!\nВаш платеж за аренду успешно получен🎉')
        await bot.send_message(chat_id=id_chat, text='[ОПЛАТА] Пользователь оплатил')
    elif 'landlord_no_reaction_cb' in data:
        await bot.send_message(chat_id=id_chat, text='[ОПЛАТА] Пользователь НЕ оплатил', reply_markup=stoped_keyboard(us_id))
        await spam_scheduler(us_id)
    elif 'stop_spam_cb' in data:
        await stop_spam_scheduler(us_id)

@payment_router.message(Command('start'))
async def go_menu(message: types.Message, state: FSMContext):
    from handlers.run import start_message
    await start_message(message, state)
