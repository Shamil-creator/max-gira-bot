from aiogram import Bot, types, Router
from aiogram.types import Message, CallbackQuery,MessageEntity
from aiogram.filters.command import Command
import os
import asyncio
import logging
from aiogram import F
from aiogram.types.input_file import FSInputFile
import asyncpg
from handlers.add_new_water_meter_readings import hot_or_cold_keyboard
from handlers.config import config
from aiogram.fsm.state import State
from aiogram.fsm.context import FSMContext
import psycopg2
from aiogram.types import InputMediaPhoto, InputMediaVideo, FSInputFile
import schedule
import time
from handlers.meter_readings import get_meter_readings_keyboard
from states.auth_states import Auth_States
from states.meter_redings_state import Meter_Readings_States
from states.notifications_state import NotificationsStates
from states.technical_request_states import Technical_States
import aiofiles


async def get_data(query: str, *params):
    conn = None
    try:
        conn = await asyncpg.connect(config.db_connection)
        return await conn.fetch(query, *params)
    except Exception as e:
        print(f"Ошибка: {e}")
        return None
    finally:
        if conn:
            await conn.close()


async def _execute(query: str, *params):
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

run_router = Router()





def smart_keyboard_mr(all_mr):
    buttons_row = []
    has_water = 'wr' in all_mr
    has_electricity = 'el' in all_mr
     
    
    if has_water:
        buttons_row.append(types.InlineKeyboardButton(text='Вода', callback_data='enter_water_cb'))
    if has_electricity:
        buttons_row.append(types.InlineKeyboardButton(text='Электричество', callback_data='enter_electricity_cb'))
    if buttons_row:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            buttons_row, 
            # [types.InlineKeyboardButton(text='В меню', callback_data='go_menu_gmr')]
        ])
    else:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text='В меню', callback_data='go_menu_gmr')]
        ])
    
    return keyboard

def get_new_meter_readings_keyboard():
    buttons = [
        [types.InlineKeyboardButton(text='Электричество', callback_data='enter_new_el_cb'), types.InlineKeyboardButton(text='Вода', callback_data='enter_new_water_cb')],
        [types.InlineKeyboardButton(text='В меню',callback_data='go_menu_new_gmr')]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons, resize_keyboard=True)
    return keyboard

async def check_mr_for_user_in_db(id_us):
    results = await get_data('SELECT COUNT(*) <> 0 AS mr_status FROM us_readings WHERE business_id = (SELECT id_business FROM users WHERE User_Id = $1)',str(id_us))
    for result in results:
        status = result['mr_status']
    return status

def go_menu_btn():
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text='В меню', callback_data='cancel_menu_cb')]
        ]
    )
    return keyboard

def get_menu_keyboard(has_meters: bool = True):
    buttons = [
        [types.KeyboardButton(text='Уведомления🛎', style="primary"), types.KeyboardButton(text='Профиль👤', style="primary")],
    ]
    if has_meters:
        buttons.append([types.KeyboardButton(text='Показания счетчиков', style="primary")])
    buttons.extend([
        [types.KeyboardButton(text='Техническая заявка', style="primary")],
        [types.KeyboardButton(text='Мои счета📁', style="primary")],
    ])
    keyboard = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard


async def build_menu_keyboard(user_id):
    rows = await get_data(
        'SELECT COUNT(*) > 0 AS has_meters FROM us_readings '
        'WHERE business_id = (SELECT id_business FROM users WHERE User_Id = $1)',
        str(user_id),
    )
    has_meters = bool(rows[0]['has_meters']) if rows else False
    return get_menu_keyboard(has_meters=has_meters)

async def get_info_business(id):
    us_businesses = await get_data('SELECT toa.name, b.* FROM users u RIGHT JOIN Bussines b ON b.id = u.id_business JOIN Type_of_Activity toa ON b.id_type_of_activity = toa.id WHERE u.User_Id = $1', str(id))
    return us_businesses

async def get_form_of_doing_info_business(id):
    fod_name = ''
    us_businesses = await get_data('SELECT fod.name FROM users u RIGHT JOIN Bussines b ON b.id = u.id_business JOIN form_of_doing_business fod ON b.id_form = fod.id WHERE u.User_Id = $1', str(id))
    for us_fod in us_businesses:
        fod_name=us_fod['name']
    return fod_name

async def get_readings_info(id):
    str_el = ''
    str_cw = ''
    str_hw = ''
    us_record = await get_data('SELECT ur.number_counter, tc.name FROM us_readings ur JOIN type_counter tc ON ur.counter_type_id = tc.id WHERE ur.business_id = (SELECT id_business FROM users WHERE User_Id = $1)', str(id))
    for us_list in us_record:
        if us_list['name'] == 'Электричество':
            str_el+=f'{us_list['number_counter']},'
        elif us_list['name'] == 'Холодная вода':
            str_cw+=f'{us_list['number_counter']},'
        elif us_list['name'] == 'Горячая вода':
            str_hw+=f'{us_list['number_counter']},'
    str_el = str_el[:-1]
    str_cw = str_cw[:-1]
    str_hw = str_hw[:-1]
    return str_el, str_cw, str_hw
@run_router.message(Command('start'))
async def start_message(message: types.Message, state: FSMContext):
    from main import bot
    from handlers.reg_user import get_type_business_keyboard
    from states.registation_states import RegStates
    id = message.chat.id
    us_data = await state.get_data()
    checkUserRecords = await get_data('SELECT 0 <> count(*) AS bool_check  FROM Users WHERE User_Id = $1', str(id))
    bool_check = [checkUserRecord['bool_check'] for checkUserRecord in checkUserRecords]
    search_dir = 'Действующие Арендаторы. Договора'
    await state.update_data(counter_status_cw = False)
    await state.update_data(counter_status_hw = False)
    await state.update_data(counter_status_el = False)
    print(bool_check[0])
    if bool_check[0]:
        current_username = message.from_user.username or ''
        await _execute(
            'UPDATE users SET username = $1 WHERE user_id = $2',
            current_username, str(id),
        )
        await state.set_state(Auth_States.menu_state)
        await message.answer('Вы в меню', reply_markup=await build_menu_keyboard(id))
    else:
        await state.set_state(RegStates.enterINN_state)
        # keyboard = get_type_business_keyboard()
        await message.answer('Пожалуйста напишите ваш ИНН')

@run_router.message(Auth_States.menu_state)
async def get_menu(message: types.Message, state:FSMContext):
    from handlers.notifications import get_menu_notification_keyboard
    from main import bot,redis as r
    id_us = message.chat.id
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id - 1)
    await message.delete()
    if message.text == 'Профиль👤':
        records_list = await get_info_business(id_us)
        str_el,str_cw,str_hw = await get_readings_info(id_us)
        print(records_list)
        if records_list:
            for list in records_list:
                name = list['name_company']
                square = list['square']
                agreement = list['agreement']
                acceptance_certificate = list['acceptance_certificate']
                bid = list['bid']
                end_date_agreement = list['end_date_agreement']
            await message.answer(f'Наименование: <b>{name}</b>\n📝Договор: <b>{agreement}</b>\nДата прекращения договора: <b>{end_date_agreement}</b>\nАкт п/п: <b>{acceptance_certificate}</b>\nЕжемесячный платеж по аренде: <b>{bid}</b>\nПлощадь: <b>{square}</b>\n\nНомера счетчиков:\n🚰  Холодная вода: <b>{str_cw}</b>\n\n🔥 Горячая вода: <b>{str_hw}</b>\n\n⚡️ Электроэнергия: <b>{str_el}</b>',parse_mode='HTML')
        await state.set_state(Auth_States.menu_state)
        await message.answer('Вы в меню', reply_markup=await build_menu_keyboard(id_us))
        
    elif message.text == 'Техническая заявка':
        await state.set_state(Technical_States.get_problem_state)
        await message.answer('Пожалуйста опишите вашу проблему',reply_markup=go_menu_btn())
    elif message.text == 'Уведомления🛎':
        await state.set_state(NotificationsStates.Notify_Menu_State)
        await message.answer('Выберите дальнейшее действие', reply_markup=get_menu_notification_keyboard())
    elif message.text == 'Мои счета📁':
        records_ids = await get_data('SELECT id_business FROM users WHERE User_Id = $1', str(id_us))
        for ids in records_ids:
           id_business = int(ids['id_business'])
        files_list = []
        record_files_list = await get_data('SELECT file_id, file_name FROM business_documents WHERE id_business = $1 ORDER BY date_added', id_business)
        if not record_files_list:
            await message.answer('У вас пока нет счетов, вы в меню', reply_markup=await build_menu_keyboard(id_us))
        else:
            await message.answer('Ваши документы👇')
            for file in record_files_list:
                try:
                    # Извлекаем сохраненное имя или ставим стандартное
                    fname = file.get('file_name') or "Счет.docx"
                    await message.answer_document(file['file_id'], filename=fname)
                except Exception as e:
                    print('Ошибка с отправкой файла')
                    await message.answer('Счет был поврежден😓')
            await message.answer('--------------------\nВы в меню', reply_markup=await build_menu_keyboard(id_us))
    elif message.text == 'Показания счетчиков':
        await state.update_data(submitted_readings={})
        us_data = await state.get_data()
        key = f"user:{id_us}:list_hot_water"
        await r.delete(key)
        results = await get_data('SELECT COUNT(*) <> 0 AS check_mr, COUNT(*) FROM us_readings WHERE business_id = (SELECT id_business FROM users WHERE User_Id = $1)',str(id_us))
        check_mr = False
        for result in results:
            check_mr = result['check_mr']
        if not check_mr:
            await state.set_state(Auth_States.menu_state)
            await message.answer('У вас нет зарегистрированных счетчиков.\nВы в меню', reply_markup=await build_menu_keyboard(id_us))
        else:
            btns = []
            hw = us_data.get('counter_status_hw')
            cw = us_data.get('counter_status_cw')
            el = us_data.get('counter_status_el')
            if (not hw or hw == False) or (not cw or cw == False):
                btns.append('wr')
            if not el or el == False:
                btns.append('el')

            keyboard = smart_keyboard_mr(btns)
            rows_count = sum(len(row) for row in keyboard.inline_keyboard)
            if rows_count > 1:
                await message.answer('Ждем от вас показания счетчиков, выберите, какой счетчик хотите заполнить', reply_markup=keyboard)
            else:
                await state.set_state(Auth_States.menu_state)
                await message.answer('В этом месяце вы заполнили все показатели.\nВы в меню', reply_markup=await build_menu_keyboard(id_us))
    else:
        await message.answer('Мы не поняли, что вы хотите сказать, попробуйте ещё раз', reply_markup=go_menu_btn())
        
@run_router.callback_query(F.data == 'submit_readings_from_reminder')
async def submit_readings_from_reminder(call: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Подать показания' из ежемесячного напоминания"""
    from main import redis as r
    id_us = call.message.chat.id
    await call.message.delete()
    await state.update_data(submitted_readings={})
    us_data = await state.get_data()
    results = await get_data(
        'SELECT COUNT(*) <> 0 AS check_mr, COUNT(*) FROM us_readings '
        'WHERE business_id = (SELECT id_business FROM users WHERE User_Id = $1)',
        str(id_us)
    )
    check_mr = False
    for result in results:
        check_mr = result['check_mr']
    if check_mr:
        btns = []
        hw = us_data.get('counter_status_hw')
        cw = us_data.get('counter_status_cw')
        el = us_data.get('counter_status_el')
        if (not hw or hw == False) or (not cw or cw == False):
            btns.append('wr')
        if not el or el == False:
            btns.append('el')
        keyboard = smart_keyboard_mr(btns)
        rows_count = sum(len(row) for row in keyboard.inline_keyboard)
        if rows_count > 1:
            await call.message.answer(
                'Выберите, какой счетчик хотите заполнить',
                reply_markup=keyboard
            )
        else:
            await state.set_state(Auth_States.menu_state)
            await call.message.answer(
                'В этом месяце вы заполнили все показатели.\nВы в меню',
                reply_markup=await build_menu_keyboard(id_us)
            )
    else:
        await state.set_state(Auth_States.menu_state)
        await call.message.answer(
            'У вас нет зарегистрированных счетчиков',
            reply_markup=await build_menu_keyboard(id_us)
        )

@run_router.callback_query(F.data.in_(['enter_new_el_cb','enter_new_water_cb','cancel_menu_cb', 'go_menu_new_gmr']))
async def cb(call: CallbackQuery, state: FSMContext):
    data = call.data
    id_us = call.message.chat.id
    await call.message.delete()
    if data == 'enter_new_el_cb':
        await state.set_state(Meter_Readings_States.add_new_electricity_readings)
        await call.message.answer('Введите номер счетчика ЭЛЕКТРИЧЕСТВА')
    elif data == 'enter_new_water_cb':
        await state.set_state(Meter_Readings_States.wait_ask_c_or_h_mr) 
        await call.message.answer('Пожалуйста выберите какие счетчики хотите заполнить',reply_markup=hot_or_cold_keyboard())
    elif data == 'cancel_menu_cb':
        await state.set_state(Auth_States.menu_state)
        await call.message.answer('Вы в меню', reply_markup=await build_menu_keyboard(id_us))
    elif data == 'go_menu_new_gmr':
        await state.set_state(Auth_States.menu_state)
        await call.message.answer('Вы в меню', reply_markup=await build_menu_keyboard(id_us))
        