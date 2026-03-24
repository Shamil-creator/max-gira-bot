from datetime import datetime, date
import tempfile
from docx import Document
from aiogram import Bot, types, Router
from aiogram.types import Message, CallbackQuery,MessageEntity
from aiogram.filters.command import Command
import os
import asyncio
import logging
from aiogram import F
from dateutil.relativedelta import relativedelta
from aiogram.types.input_file import FSInputFile
import asyncpg
from handlers.config import config
from aiogram.fsm.state import State
from aiogram.fsm.context import FSMContext
import psycopg2
from aiogram.types import InputMediaPhoto, InputMediaVideo, FSInputFile
import schedule
import time
from states.notifications_state import NotificationsStates
from states.auth_states import Auth_States
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import sys

async def get_data(query: str, *params):
    try:
        conn = await asyncpg.connect(config.db_connection)
        result = await conn.fetch(query,*params)
        await conn.close()
        return result
    except Exception as e: 
        print(f"Ошибка: {e}")
        return None
    
notifications_router = Router()

def ask_payment_tenant_keyboard(id):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="Уведомить о получении", 
                callback_data=f"get_notify_term_cb:{id}"
            ),
        ]
    ])
    return keyboard

def go_back_from_agreement_termination_of_the_contract():
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text='Отмена', callback_data='cancel_agreement_termination_cb')]
        ]
    )
    return keyboard

def redact_word_termination(date_now, agreement, description, company_name):
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
        doc = Document('docs/Уведомление_о_расторжении_шаблон.docx')
        agreement_list = agreement.split(' ')
        agr_num = agreement_list[0] if len(agreement_list) > 0 else ""
        agr_date = agreement_list[1] if len(agreement_list) > 1 else ""
        for paragraph in doc.paragraphs:
            if 'dateagreement' in paragraph.text:
                paragraph.text = paragraph.text.replace('dateagreement', agr_date)
            if 'Replace_arendator_info' in paragraph.text:
                paragraph.text = paragraph.text.replace('Replace_arendator_info', company_name)
            if 'numberagreement' in paragraph.text:
                paragraph.text = paragraph.text.replace('numberagreement', agr_num)
            if 'descriptionagreement' in paragraph.text:
                paragraph.text = paragraph.text.replace('descriptionagreement', description)
            if 'nowdate' in paragraph.text:
                paragraph.text = paragraph.text.replace('nowdate', date_now)
        
        doc.save(tmp_file.name)
        return tmp_file.name


def yes_or_no_termination_keyboard():
    buttons = [
        [types.InlineKeyboardButton(text='Да',style="danger", callback_data='yes_termination_cb')],
        [types.InlineKeyboardButton(text='Нет',style="success", callback_data='no_termination_cb')],
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons, resize_keyboard=True)
    return keyboard

def get_menu_notification_keyboard():
    buttons = [
        [types.InlineKeyboardButton(text='Согласование ремонтных работ', callback_data='coordination_of_repair_work_cb')],
        [types.InlineKeyboardButton(text='Уведомить о растрожении',style="danger", callback_data='notify_of_termination_cb')],
        [types.InlineKeyboardButton(text='Вернуться в меню',style="primary", callback_data='go_menu_cb')]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons, resize_keyboard=True)
    return keyboard

@notifications_router.message(Command('start'))
async def go_menu(message: types.Message, state: FSMContext):
    from handlers.run import start_message
    await start_message(message, state)

@notifications_router.message(NotificationsStates.Notify_Menu_State)
async def get_menu(message: types.Message, state:FSMContext):
    if message.text == 'Профиль👤':
        pass
    elif message.text == 'Техническая заявка':
        pass
    else:
        await message.answer('Выберите дальнейшее действие', reply_markup=get_menu_notification_keyboard())

@notifications_router.callback_query(F.data.startswith('get_notify_term_cb'))
async def callback(call: CallbackQuery, state: FSMContext):
    from main import bot
    data = call.data
    callstart,id = data.split(':')
    await call.message.edit_reply_markup(reply_markup=None)
    await bot.send_message(chat_id=id, text='Арендодатель ознакомился с вашим уведомлением')

@notifications_router.callback_query(F.data.in_(['notify_of_termination_cb', 'agreement_termination_of_the_contract_cb','coordination_of_repair_work_cb', 'go_menu_cb', 'yes_termination_cb', 'no_termination_cb','cancel_agreement_termination_cb']))
async def callback(call: CallbackQuery, state: FSMContext):
    from states.repair_work_states import Repair_State
    from handlers.run import get_info_business,get_menu_keyboard
    from main import bot
    data = call.data
    await call.message.delete()
    if data == 'notify_of_termination_cb':
        await call.message.answer('Вы хотите уведомить о растрожении?', reply_markup=yes_or_no_termination_keyboard())
    elif data == 'agreement_termination_of_the_contract_cb':
        try:
            doc_path = redact_word_termination()
            document = FSInputFile(doc_path)
            await call.message.answer_document(document=document)
            await call.message.answer('Ожидаем от Вас документ о расторжении',reply_markup=go_back_from_agreement_termination_of_the_contract())
            os.unlink(doc_path)
            await state.set_state(NotificationsStates.Wait_document_for_termination_State)
        
        except Exception as e:
            await call.message.answer(f"Ошибка: {e}")
    elif data == 'coordination_of_repair_work_cb':
        id_us = call.message.chat.id
        records_list = await get_info_business(id_us)
        if records_list:
            for list in records_list:
                toa_name = list['name']
                name = list['name_company']
                agreement = list['agreement']
        id_admin = config.chanel_id.get_secret_value()
        await call.message.answer('Ваша заявка принята. Техническая служба и арендодатель уведомлены')
        await bot.send_message(
            chat_id=id_admin,
            text=f'[РЕМОНТ] Вид деятельности: {toa_name}\n\nНаименование: {name}\n\nДоговор📝 - {agreement}\n\nХочет провести ремонтные работы',
        )
        
        await state.set_state(Auth_States.menu_state)
        await call.message.answer('Вы в меню', reply_markup=get_menu_keyboard())
    elif data == 'go_menu_cb':
        from handlers.run import get_menu_keyboard
        await state.set_state(Auth_States.menu_state)
        await call.message.answer('Вы в меню', reply_markup=get_menu_keyboard())
    elif data == 'yes_termination_cb':
        await state.set_state(NotificationsStates.Notify_of_termination_State)
        await call.message.answer(''''Пожалуйста напишите причину расторжения "В связи ..."''')
    elif data == 'no_termination_cb':
        await state.set_state(NotificationsStates.Notify_Menu_State)
        await call.message.answer('Выберите дальнейшее действие', reply_markup=get_menu_notification_keyboard())
    elif data == 'cancel_agreement_termination_cb':
        await state.set_state(NotificationsStates.Notify_Menu_State)
        await call.message.answer('Выберите дальнейшее действие', reply_markup=get_menu_notification_keyboard())

@notifications_router.message(NotificationsStates.Wait_document_for_termination_State)
async def get_docs(msg: Message, state:FSMContext):
    from main import bot
    from handlers.config import config
    id_admin = config.chanel_id.get_secret_value()
    if msg.document:
        file_id = msg.document.file_id
        await msg.answer('Документ получен')
        await bot.send_document(
            chat_id=id_admin,
            document=file_id,
            caption=f"[ДОКУМЕНТЫ] 📄 Документ от пользователя {msg.from_user.full_name}\n"
        )
    else:
        await msg.answer('Пожалуйста отправьте документ или нажмите кнопку отмена')

@notifications_router.message(NotificationsStates.Notify_of_termination_State)
async def get_notify_of_termination_info(message: types.Message, state: FSMContext):
    from main import bot
    from states.auth_states import Auth_States
    from handlers.run import get_menu_keyboard,get_info_business
    from handlers.config import config
    id_us = message.chat.id
    records_list = await get_info_business(id_us)
    today_str = date.today().strftime('%d.%m.%Y')
    next_month_str = (date.today() + relativedelta(months=1)).strftime('%d.%m.%Y')
    if records_list:
        for list in records_list:
            name = list['name_company']
            agreement = str(list['agreement'])
            print(agreement)
    #         text = f'Вид деятельности:{toa_name}\n\nУважаемый Арендодатель, настоящим сообщением уведомляю Вас о расторжении Договора аренды {number_agreement} от {date_agreement}, с {today}, в связи {message.text}\n'
    # text +=f'{name}'
    chat_id = config.chanel_id.get_secret_value()
    msg = message.text
    doc_path = redact_word_termination(next_month_str, agreement, msg, name)
    document = FSInputFile(doc_path)
    # await message.answer_document(document=document)
    await message.answer('Отправили уведомление о рассторжении арендодателю')
    keyboard = ask_payment_tenant_keyboard(id_us)
    await bot.send_document(chat_id=chat_id, document=document, caption='[РАСТОРЖЕНИЕ] Уведомление от арендатора', reply_markup=keyboard)
    # await bot.send_message(chat_id=chat_id, text=text,reply_markup=keyboard)
    await state.set_state(Auth_States.menu_state)
    await message.answer('Вы в меню', reply_markup=get_menu_keyboard())
