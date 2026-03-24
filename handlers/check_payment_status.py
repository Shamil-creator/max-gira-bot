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
    try:
        import asyncpg
        conn = await asyncpg.connect(config.db_connection)
        result = await conn.fetch(query, *params)
        await conn.close()
        return result
    except Exception as e: 
        logging.error(f"Ошибка БД: {e}")
        return None

async def new_data_insert(query: str, *params):
    try:
        conn = await asyncpg.connect(config.db_connection)
        result = await conn.execute(query,*params)
        return result
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

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
    from main import bot
    await bot.send_message(chat_id=id, text='Здравствуйте! Напоминаем вам о необходимости оплаты ежемесячного арендного платежа. Укажите вы уже внесли платёж?', reply_markup=ask_payment_tenant_keyboard(id))
    # await bot.send_message(chat_id=id, text='Здравствуйте! Напоминаем вам о необходимости оплаты ежемесячного арендного платежа. Укажите вы уже внесли платёж?')

async def get_mr_message_every_month(id):
    from main import bot
    await bot.send_message(chat_id=id, text='Здравствуйте! Необходимо внести показания счетчиков до 10 числа текущего месяца')
    
async def get_invoice_msg_every_month(id):
    from main import bot
    records_list = await get_info_business(id)
    fod_name = await get_form_of_doing_info_business(id)
    if records_list:
        for list in records_list:
            name = list['name_company']
            agreement = list['agreement']
            bid = list['bid']
            number_act = list['number_act']
    if number_act is not None:
        number_act = int(number_act) + 1
    else:
        number_act = 1
    full_name = f'''{fod_name} "{name}"'''
    file_path = await create_invoice_for_payment_for_user(number_act, full_name, agreement, bid)
    document = FSInputFile(file_path)
    number_act = int(number_act)+1
    await new_data_insert('UPDATE bussines SET number_act = $1 WHERE name_company = $2',int(number_act), name)
    sent_message = await bot.send_document(chat_id=id, document=document, caption='Здравствуйте! Ваш счет за текущий месяц')
    today_date = date.today()
    file_id = sent_message.document.file_id
    records = await get_data('SELECT id_business FROM users WHERE User_Id = $1',str(id))
    id_business = records[0]['id_business']
    await new_data_insert('INSERT INTO business_documents(id_business,file_id, date_added) VALUES ($1, $2, $3)',id_business, file_id, today_date)

async def get_act_of_payment(id):
    from main import bot
    records_list = await get_info_business(id)
    if records_list:
        for list in records_list:
            name = list['name_company']
            square = list['square']
            agreement = list['agreement']
            acceptance_certificate = list['acceptance_certificate']
            bid = list['bid']
            surname = list['surname']
            first_name = list['first_name']
            patronymic = list['patronymic']
            number_act = list['number_act']
    today = datetime.now()

    # Начало текущего месяца
    start_of_month = today.replace(day=1)

    # Конец текущего месяца
    last_day = calendar.monthrange(today.year, today.month)[1]
    end_of_month = today.replace(day=last_day)
    end_str = end_of_month.strftime("%d.%m.%Y")
    full_name_tenant = f'{surname} {first_name} {patronymic}'
    print(f'Проверка на отправляемое {full_name_tenant}')
    file_path = await create_layoat_for_user('ООО ГИРА', name, end_str, bid, square, agreement, full_name_tenant, number_act)
    document = FSInputFile(file_path)
    number_act = int(number_act)+1
    await new_data_insert('UPDATE bussines SET number_act = $1 WHERE square = $2 AND name_company = $3',int(number_act),square, name)
    sent_message = await bot.send_document(chat_id=id, document=document, caption='Доброе утро! Ваш Акт за текущий месяц')
    today_date = date.today()
    file_id = sent_message.document.file_id
    records = await get_data('SELECT id_business FROM users WHERE User_Id = $1',str(id))
    id_business = records[0]['id_business']
    await new_data_insert('INSERT INTO business_documents(id_business,file_id, date_added) VALUES ($1, $2, $3)',id_business, file_id, today_date)


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
