from datetime import datetime
import tempfile
from docx import Document
from aiogram import Bot, types, Router
from aiogram.types import Message, CallbackQuery,MessageEntity
from aiogram.filters.command import Command
import os
import asyncio
import logging
from aiogram import F
from datetime import datetime
from aiogram.types.input_file import FSInputFile, InputFile
import asyncpg
from handlers.config import config
from aiogram.fsm.state import State
from aiogram.fsm.context import FSMContext
import psycopg2
from aiogram.types import InputMediaPhoto, InputMediaVideo, FSInputFile
import schedule
import time
from states.meter_redings_state import Meter_Readings_States
import aiofiles
from functools import lru_cache
from states.auth_states import Auth_States
from handlers.images_cache import image_cache

_image_cache = None

def smart_keyboard_hot_cold_w_mr(all_mr):
    buttons_row = []
    has_cold_water = 'cw' in all_mr
    has_hot_water = 'hw' in all_mr
    
    if has_cold_water:
        buttons_row.append(types.InlineKeyboardButton(text="Холодная вода", callback_data="selected_mr_cw"))
    if has_hot_water:
        buttons_row.append(types.InlineKeyboardButton(text="Горячая вода", callback_data="selected_mr_hw"))
    if buttons_row:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            buttons_row
            # [types.InlineKeyboardButton(text='В меню', callback_data='go_menu_gmr')]
        ])
    # else:
    #     keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
    #         [types.InlineKeyboardButton(text='В меню', callback_data='go_menu_gmr')]
    #     ])
    
    return keyboard

async def get_water_image():
    global _image_cache
    if _image_cache is None:
        with open('images/water.png', 'rb') as f:
            _image_cache = InputFile(f)
    return _image_cache

async def get_data(query: str, *params):
    try:
        conn = await asyncpg.connect(config.db_connection)
        result = await conn.fetch(query,*params)
        await conn.close()
        return result
    except Exception as e: 
        print(f"Ошибка: {e}")
        return None
    
meter_readings_router = Router()

async def check_count_mr_for_type(id_us, type_id):
    records = await get_data('SELECT id_business FROM users WHERE User_Id = $1',str(id_us))
    id_business = None
    for record in records:
        id_business = record['id_business']
    
    if id_business is None:
        return 0
        
    results = await get_data('SELECT COUNT(id) AS count_row FROM us_readings WHERE business_id = $1 AND counter_type_id = $2',int(id_business), type_id)
    count = 0
    for result in results:
        count = result['count_row']
    return count

async def get_sheet_name(id_us):
    results = await get_data('SELECT sheets_name FROM users WHERE User_Id = $1',str(id_us))
    sheet_name = "Неизвестно"
    if results:
        for record in results:
            sheet_name = record['sheets_name']
    return sheet_name

async def check_mr_for_user_in_db(id_us, type_id):
    all_mr_us = []
    records = await get_data('SELECT id_business FROM users WHERE User_Id = $1',str(id_us))
    id_business = None
    for record in records:
        id_business = record['id_business']
        
    if id_business is None:
        return []
        
    results = await get_data('SELECT id, number_counter FROM us_readings WHERE business_id = $1 AND counter_type_id = $2 ORDER BY counter_type_id',int(id_business), type_id)
    for result in results:
        all_mr_us.append(result['number_counter'])
    return all_mr_us

def create_dynamic_keyboard(all_mr_us, type_id):
    buttons = []
    all_mr_us = list(set(all_mr_us))
    for mr in all_mr_us:
        if type_id == 1:
            cb = f'mr_enter_cw_{mr}'
        elif type_id == 2:
            cb = f'mr_enter_el_{mr}'
        elif type_id == 3:
            cb = f'mr_enter_hw_{mr}'
        print(cb)
        buttons.append(
            types.InlineKeyboardButton(text=mr, callback_data=cb)
        )
    buttons.append(types.InlineKeyboardButton(text='Назад', callback_data='gb_in_enter_mr'))
    inline_keyboard = [[btn] for btn in buttons]
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return keyboard

def hot_or_cold_keyboard():
    buttons = [
        [types.InlineKeyboardButton(text="Холодная вода", callback_data="selected_mr_cw")],
        [types.InlineKeyboardButton(text="Горячая вода", callback_data="selected_mr_hw")],
        [types.InlineKeyboardButton(text='Назад', callback_data='hoc_go_back_cb')]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons, resize_keyboard=True)
    return keyboard

async def generate_keyboard_hw(us_id):
    from main import redis as r
    buttons = []
    all_mr = []
    records_list = await get_data('SELECT number_counter FROM us_readingsWHERE counter_type_id = 3')
    key = f'hot_water_mr{us_id}'
    all_mr = [record['number_counter'] for record in records_list]
    await r.lpush(key,*all_mr)
    for counter, mr in enumerate(all_mr, start=1):
        cb_data = f'mr_hw_{mr}'
        str_counter = str(counter)
        buttons.append(
            types.InlineKeyboardButton(text=str_counter, callback_data=cb_data)
        )
    inline_keyboard = []
    for i in range(0, len(buttons), 2):
        inline_keyboard.append(buttons[i:i+2])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return keyboard

async def generate_keyboard_el(us_id):
    from main import redis as r
    buttons = []
    all_mr = []

    records_list = await get_data('SELECT number_counter FROM us_readings WHERE counter_type_id = 2')
    key = f'electricity_mr:{us_id}'
    all_mr = [record['number_counter'] for record in records_list]
    await r.lpush(key,*all_mr)
    for counter, mr in enumerate(all_mr, start=1):
        cb_data = f'mr_el_{mr}'
        str_counter = str(counter)
        buttons.append(
            types.InlineKeyboardButton(text=str_counter, callback_data=cb_data)
        )
    inline_keyboard = []
    for i in range(0, len(buttons), 2):
        inline_keyboard.append(buttons[i:i+2])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return keyboard

def get_meter_readings_keyboard():
    buttons = [
        [types.InlineKeyboardButton(text='Электричество', callback_data='enter_electricity_cb'), types.InlineKeyboardButton(text='Вода', callback_data='enter_water_cb')],
        [types.InlineKeyboardButton(text='В меню',callback_data='go_menu_gmr')]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons, resize_keyboard=True)
    return keyboard

@meter_readings_router.callback_query(F.data.startswith('mr_enter_'))
async def callback(call: CallbackQuery, state: FSMContext):
    data = call.data
    mass = data.split('_')
    this_mr_type = mass[2]
    image_electricity = image_cache.get_electricity()
    image_water = image_cache.get_water()
    # if not os.path.exists('images/electricity.png'):
    #     await call.message.answer("⚠️ Файл electricity.png не найден в папке images/")
    #     return
    # image_electricity = FSInputFile(path='images/electricity.png')
    # if not os.path.exists('images/water.png'):
    #     await call.message.answer("⚠️ Файл water.png не найден в папке images/")
    #     return
    # image_water = FSInputFile(path='images/water.png')
    number = data[12:]
    await call.message.delete()
    if this_mr_type == 'cw':
        await call.message.answer_photo(photo=image_water, caption=f'Введите показания счетчика ХОЛОДНОЙ воды под номером - {number}. Введите значение состоящее из 5 цифр')
        await state.set_state(Meter_Readings_States.enter_cold_water)
    elif this_mr_type == 'hw':
        await call.message.answer_photo(photo=image_water, caption=f'Введите показания счетчика ГОРЯЧЕЙ воды под номером - {number}. Введите значение состоящее из 5 цифр')
        await state.set_state(Meter_Readings_States.enter_hot_water)
    elif this_mr_type == 'el':
        await state.set_state(Meter_Readings_States.enter_electricity)
        await call.message.answer_photo(
            photo=image_electricity,
            caption="Введите показания счетчика электричества. Введите значение состоящее из 6 цифр"
        )
    await state.update_data(selected_mr = number)

@meter_readings_router.callback_query(F.data.in_(['selected_mr_cw','selected_mr_hw','hoc_go_back_cb']))
async def callback(call: CallbackQuery, state: FSMContext):
    from main import redis as r
    data = call.data
    await call.message.delete()
    id_us = call.message.chat.id
    image_water = image_cache.get_water()
    # if not os.path.exists('images/water.png'):
    #     await call.message.answer("⚠️ Файл water.png не найден в папке images/")
    #     return
    # image_water = FSInputFile(path='images/water.png')
    if data == 'selected_mr_cw':
        await state.update_data(sum_mr_сw = 0)
        type_id = 1
        await state.set_state(Meter_Readings_States.add_new_cold_water_readings)
        count = await check_count_mr_for_type(id_us, type_id)
        print(count)
        if count>1:
            key = f"user:{id_us}:list_cold_water"
            if await r.llen(key) > 0:
                all_mr = await r.lrange(key, 0, -1)
            else:
                all_mr = await check_mr_for_user_in_db(id_us, type_id)
                if all_mr:
                    await r.rpush(key, *all_mr)
            mr = await r.lrange(key,0,-1)
            keyboard = create_dynamic_keyboard(all_mr, type_id)
            await call.message.answer('Выберите номер счетчика',reply_markup=keyboard)
        elif count == 1:
            await state.set_state(Meter_Readings_States.one_cold_water_readings_state)
            await call.message.answer_photo(photo=image_water, caption="Введите показания счетчика ХОЛОДНОЙ воды. Введите значение состоящее из 5 цифр")
        elif count < 1:
            await state.set_state(Meter_Readings_States.add_new_cold_water_readings)
            await call.message.answer('Введите номер счетчика ХОЛОДНОЙ воды')
    elif data == 'selected_mr_hw':
        await state.update_data(sum_mr_hw = 0)
        type_id = 3
        count = await check_count_mr_for_type(id_us, type_id)
        print(count)
        if count>1:
            key = f"user:{id_us}:list_hot_water"
            if await r.llen(key) > 0:
                all_mr = await r.lrange(key, 0, -1)
            else:
                all_mr = await check_mr_for_user_in_db(id_us, type_id)
                if all_mr:
                    await r.rpush(key, *all_mr)
            mr = await r.lrange(key,0,-1)
            keyboard = create_dynamic_keyboard(all_mr, type_id)
            await call.message.answer('Выберите номер счетчика',reply_markup=keyboard)
        elif count == 1:
            await state.set_state(Meter_Readings_States.one_hot_water_readings_state)
            await call.message.answer_photo(photo=image_water, caption="Введите показания счетчика ГОРЯЧЕЙ воды. Введите значение состоящее из 5 цифр")
        elif count < 1:
            await state.set_state(Meter_Readings_States.add_new_hot_water_readings)
            await call.message.answer('Введите номер счетчика ГОРЯЧЕЙ воды')
    elif data == 'hoc_go_back_cb':
        await state.set_state(Meter_Readings_States.wait_meter_readings_state)
        await call.message.answer('Какие показания счетчиков хотите заполнить?',reply_markup=get_meter_readings_keyboard())
        


@meter_readings_router.message(Meter_Readings_States.wait_meter_readings_state)
async def msg(message: Message, state: FSMContext):
    await message.answer('Нам не удалось понять, что вы хотите сделать, пожалуйста нажмите кнопку "Электричество" или "Вода", чтоб ввести показатели', reply_markup=get_meter_readings_keyboard())

@meter_readings_router.callback_query(F.data.in_(['enter_electricity_cb','enter_water_cb','gb_in_enter_mr', 'go_menu_gmr']))
async def cb(call: CallbackQuery, state: FSMContext):
    from main import redis as r
    from handlers.run import get_menu_keyboard
    data = call.data
    await call.message.delete()
    us_data = await state.get_data()
    id_us = call.message.chat.id
    image_electricity = image_cache.get_electricity()
    if data == 'enter_water_cb':
        btns = []
        hw = us_data.get('counter_status_hw')
        cw = us_data.get('counter_status_cw')
        if not hw or hw == False:
            btns.append('hw')
        if not cw or cw == False:
            btns.append('cw')

        keyboard = smart_keyboard_hot_cold_w_mr(btns)
        await call.message.answer('Пожалуйста выберите счетчики',reply_markup=keyboard)
    elif data == 'enter_electricity_cb':
        await state.update_data(sum_mr_el = 0)
        type_id = 2

        count = await check_count_mr_for_type(id_us, type_id)
        print(f'Мы тут - {count}')
        if count>1:
            key = f"user:{id_us}:list_electricity"
            
            if await r.llen(key) > 0:
                all_mr = await r.lrange(key, 0, -1)
            else:
                all_mr = await check_mr_for_user_in_db(id_us, type_id)
                if all_mr:
                    await r.rpush(key, *all_mr)
            mr = await r.lrange(key,0,-1)
            keyboard = create_dynamic_keyboard(all_mr, type_id)
            await call.message.answer('Выберите номер счетчика',reply_markup=keyboard)
        elif count == 1:
            await state.set_state(Meter_Readings_States.one_electricity_readings_state)
            await call.message.answer_photo(
                photo=image_electricity,
                caption="Введите показания электричества. Введите значение состоящее из 6 цифр"
            )
        elif count <= 0:
            await state.set_state(Meter_Readings_States.add_new_electricity_readings)
            await call.message.answer('Введите номер счетчика ЭЛЕКТРИЧЕСТВА')
    elif data == 'gb_in_enter_mr':
        await call.message.answer('Ждем от вас показания счетчиков, выберите, какой счетчик хотите заполнить',reply_markup=get_meter_readings_keyboard())
    elif data == 'go_menu_gmr':
        await state.set_state(Auth_States.menu_state)
        await call.message.answer('Вы в меню', reply_markup=get_menu_keyboard())

@meter_readings_router.message(Meter_Readings_States.one_cold_water_readings_state)
@meter_readings_router.message(Meter_Readings_States.one_hot_water_readings_state)
@meter_readings_router.message(Meter_Readings_States.one_electricity_readings_state)
async def message_elect(msg: Message, state: FSMContext):
    from main import bot
    from handlers.run import get_menu_keyboard,smart_keyboard_mr
    from handlers.excel_tg_test import save_mr_result_in_excel
    current_state = await state.get_state()
    check_integer = (msg.text or "").strip()
    id_us = msg.chat.id
    print(f'Проверка айди пользователя перед сохранением - {id_us}')
    await bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id - 1)
    await msg.delete()
    if msg.text == 'Отмена':
        await state.set_state(Auth_States.menu_state)
        await msg.answer('Вы в меню', reply_markup=get_menu_keyboard())
    else:
        if current_state == Meter_Readings_States.one_electricity_readings_state:
            if check_integer.isdigit():
                if len(check_integer)==6:
                    sheet_name = await get_sheet_name(id_us)
                    await save_mr_result_in_excel(sheet_name,check_integer,2)
                    await state.update_data(counter_status_el = True)
                    us_data = await state.get_data()
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
                    if rows_count>=1:
                        await msg.answer('Ждем от вас показания счетчиков, выберите, какой счетчик хотите заполнить',reply_markup=keyboard)
                    else:
                        await state.set_state(Auth_States.menu_state)
                        await msg.answer('В этом месяце вы заполнили все показатели.\nВы в меню', reply_markup=get_menu_keyboard())
                    
                    # await msg.answer('Закончили заполнения счетчиков ЭЛЕКТРИЧЕСТВА')
                    # await state.set_state(Auth_States.menu_state)
                    # await msg.answer('Вы в меню', reply_markup=get_menu_keyboard())
                else:
                    await msg.answer(f'Неверный формат ввода значний Электричества. Попробуйте снова — значение должно содержать первые 6 цифр')
            else:
                await msg.answer("Пожалуйста введите число.")
        elif current_state == Meter_Readings_States.one_hot_water_readings_state:
            if check_integer.isdigit():
                if len(check_integer)==5:
                    
                    sheet_name = await get_sheet_name(id_us)
                    await save_mr_result_in_excel(sheet_name,check_integer,3)
                    await state.update_data(counter_status_hw = True)
                    us_data = await state.get_data()
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
                    if rows_count>=1:
                        await msg.answer('Ждем от вас показания счетчиков, выберите, какой счетчик хотите заполнить',reply_markup=keyboard)
                    else:
                        await state.set_state(Auth_States.menu_state)
                        await msg.answer('В этом месяце вы заполнили все показатели.\nВы в меню', reply_markup=get_menu_keyboard())
                    # await msg.answer('Закончили заполнения счетчиков ГОРЯЧЕЙ воды')
                    # await state.set_state(Auth_States.menu_state)
                    # await msg.answer('Вы в меню', reply_markup=get_menu_keyboard())
                else:
                    await msg.answer(f'Неверный формат ввода значний Горячей Воды. Попробуйте снова — значение должно содержать первые 5 цифр')
            else:
                await msg.answer("Пожалуйста введите число.")
        elif current_state == Meter_Readings_States.one_cold_water_readings_state:
            if check_integer.isdigit():
                if len(check_integer)==5:
                    sheet_name = await get_sheet_name(id_us)
                    await save_mr_result_in_excel(sheet_name,check_integer,1)
                    await state.update_data(counter_status_cw = True)
                    us_data = await state.get_data()
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
                    if rows_count>=1:
                        await msg.answer('Ждем от вас показания счетчиков, выберите, какой счетчик хотите заполнить',reply_markup=keyboard)
                    else:
                        await state.set_state(Auth_States.menu_state)
                        await msg.answer('В этом месяце вы заполнили все показатели.\nВы в меню', reply_markup=get_menu_keyboard())
                    
                    # await msg.answer('Закончили заполнения счетчиков ХОЛОДНОЙ воды')
                    # await state.set_state(Auth_States.menu_state)
                    # await msg.answer('Вы в меню', reply_markup=get_menu_keyboard())
                else:
                    await msg.answer(f'Неверный формат ввода значний Холодной Воды. Попробуйте снова — значение должно содержать первые 5 цифр')
            else:
                await msg.answer("Пожалуйста введите число.")
        
@meter_readings_router.message(Meter_Readings_States.water_readings_state)
async def message_elect(msg: Message, state: FSMContext):
    check_integer = msg.text
    if isinstance(check_integer, int) :
        if len(check_integer)==5:
            await msg.answer(f'Увидели ваши покзатели - {check_integer}')
        else:
            await msg.answer(f'Пожалуйста введите 5 цифр')
    else:
        await msg.answer("""Пожалуйста введите число, если хотите вернуться назад, нажмите кнопку 'Отмена'""")

@meter_readings_router.message(Meter_Readings_States.add_new_cold_water_readings)
async def process_water_meter_number(message: types.Message, state: FSMContext):
    meter_number = message.text.strip()
    
    if not meter_number:
        await message.answer("❌ Номер не может быть пустым. Введите номер счетчика воды:")
        return
    data = await state.get_data()
    water_meters = data.get("water_meters", [])
    last_message_id = data.get("last_keyboard_message_id")
    water_meters.append(meter_number)
    await state.update_data(water_meters=water_meters)

@meter_readings_router.message(Meter_Readings_States.enter_hot_water)
@meter_readings_router.message(Meter_Readings_States.enter_electricity)
@meter_readings_router.message(Meter_Readings_States.enter_cold_water)
async def mess(msg: Message, state: FSMContext):
    from handlers.excel_tg_test import save_mr_result_in_excel
    from states.auth_states import Auth_States
    from main import bot,redis as r 
    from handlers.run import get_menu_keyboard
    check_integer = msg.text
    this_state = await state.get_state()
    this_data = await state.get_data()
    this_number = this_data['selected_mr']
    id_us = msg.chat.id
    await msg.delete()
    await bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id - 1)
    if this_state == Meter_Readings_States.enter_hot_water:
        if check_integer.isdigit():
            if len(check_integer)==5:
                type_id = 3
                if this_number == 0:
                    await msg.answer('Пожалуйста дождитесь отправки изображения')
                else:
                    mr_data = await state.get_data()
                    sum_do = mr_data['sum_mr_hw']
                    now_sum = int(check_integer)+int(sum_do)
                    await state.update_data(sum_mr_hw = now_sum)
                    key = f"user:{id_us}:list_hot_water"
                    all_mr = await r.lrange(key, 0, -1)
                    print(f'До очистки список - {all_mr}')
                    await msg.answer(f'Ваши показатели на счетчик №{this_number} - {check_integer} куб.метров')
                    await r.lrem(key,count=0, value = this_number)
                    all_mr = await r.lrange(key, 0, -1)
                    await state.update_data(selected_mr = 0)
                    if len(all_mr) == 0:
                        mr_data = await state.get_data()
                        sum = mr_data['sum_mr_hw']
                        print(f'Итоговая сумма получилась - {sum}')
                        sheet_name = await get_sheet_name(id_us)
                        await save_mr_result_in_excel(sheet_name,sum,3)
                        await state.update_data(counter_status_hw = True)
                        await msg.answer('Закончили заполнения счетчиков ГОРЯЧЕЙ воды')
                        await state.set_state(Auth_States.menu_state)
                        await msg.answer('Вы в меню', reply_markup=get_menu_keyboard())
                    else:
                        keyboard = create_dynamic_keyboard(all_mr, type_id)
                        await msg.answer('Выберите номер счетчика',reply_markup=keyboard)
            else:
                await msg.answer(f'Пожалуйста введите 5 цифр')
        else:
            await msg.answer("""Пожалуйста введите число. Eсли хотите вернуться назад, нажмите кнопку 'Отмена'""")
    elif this_state == Meter_Readings_States.enter_electricity:
        if check_integer.isdigit():
            if len(check_integer)==6:
                type_id = 2
                if this_number == 0:
                    await msg.answer('Пожалуйста дождитесь отправки изображения')
                else:
                    mr_data = await state.get_data()
                    sum_do = mr_data['sum_mr_el']
                    now_sum = int(check_integer)+int(sum_do)
                    await state.update_data(sum_mr_el = now_sum)
                    key = f"user:{id_us}:list_electricity"
                    all_mr = await r.lrange(key, 0, -1)
                    print(f'До очистки список - {all_mr}')
                    await msg.answer(f'Ваши показатели на счетчик №{this_number} - {check_integer} куб.метров')
                    await r.lrem(key,count=0, value = this_number)
                    all_mr = await r.lrange(key, 0, -1)
                    await state.update_data(selected_mr = 0)
                    if len(all_mr) == 0:
                        mr_data = await state.get_data()
                        sum = mr_data['sum_mr_el']
                        print(f'Итоговая сумма получилась - {sum}')
                        sheet_name = await get_sheet_name(id_us)
                        await save_mr_result_in_excel(sheet_name,sum,2)
                        await state.update_data(counter_status_el = True)
                        await msg.answer('Закончили заполнения счетчиков ЭЛЕКТРИЧЕСТВА')
                        await state.set_state(Auth_States.menu_state)
                        await msg.answer('Вы в меню', reply_markup=get_menu_keyboard())
                    else:
                        keyboard = create_dynamic_keyboard(all_mr, type_id)
                        await msg.answer('Выберите номер счетчика',reply_markup=keyboard)
            else:
                await msg.answer(f'Пожалуйста введите 6 цифр')
        else:
            await msg.answer("""Пожалуйста введите число. Eсли хотите вернуться назад, нажмите кнопку 'Отмена'""")
    elif this_state == Meter_Readings_States.enter_cold_water:
        if check_integer.isdigit():
            if len(check_integer)==5:
                type_id = 1
                if this_number == 0:
                    await msg.answer('Пожалуйста дождитесь отправки изображения')
                else:
                    mr_data = await state.get_data()
                    sum_do = mr_data['sum_mr_сw']
                    # await r.delete(key)
                    key = f"user:{id_us}:list_cold_water"
                    now_sum = int(check_integer)+int(sum_do)
                    await state.update_data(sum_mr_сw = now_sum)
                    all_mr = await r.lrange(key, 0, -1)
                    print(f'До очистки список - {all_mr}')
                    await msg.answer(f'Ваши показатели на счетчик №{this_number} - {check_integer} куб.метров')
                    await r.lrem(key,count=0, value = this_number)
                    all_mr = await r.lrange(key, 0, -1)
                    await state.update_data(selected_mr = 0)
                    if len(all_mr) == 0:
                        mr_data = await state.get_data()
                        sum = mr_data['sum_mr_сw']
                        print(f'Итоговая сумма получилась - {sum}')
                        sheet_name = await get_sheet_name(id_us)
                        await save_mr_result_in_excel(sheet_name,sum,type_id)
                        await state.update_data(counter_status_cw = True)
                        await msg.answer('Закончили заполнения счетчиков ХОЛОДНОЙ воды')
                        await state.set_state(Auth_States.menu_state)
                        await msg.answer('Вы в меню', reply_markup=get_menu_keyboard())
                    else:
                        keyboard = create_dynamic_keyboard(all_mr, type_id)
                        await msg.answer('Выберите номер счетчика',reply_markup=keyboard)
            else:
                await msg.answer(f'Пожалуйста введите 5 цифр')
        else:
            await msg.answer("""Пожалуйста введите число. Eсли хотите вернуться назад, нажмите кнопку 'Отмена'""")
