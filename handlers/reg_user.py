from datetime import datetime
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
import time
import pandas as pd
from states.auth_states import Auth_States
from states.registation_states import RegStates

reg_router = Router()

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

async def get_usname(id):
    from main import bot
    user = await bot.get_chat(id)
    usname = user.username
    return usname

def check_word_in_excel_file(word):
    file_path = 'docs/ГИРА_1006теккаа2.xlsx'
    df = pd.read_excel(file_path, sheet_name = 'Реестр')
    column_name = 'ИНН'
    row = df.loc[df['ИНН'] == int(word)]
    
    if not row.empty:
        print(f"Нашли компанию")
        return True
    else:
        print(f"Не нашли компанию")
        return False
    

async def smart_add_keyboard(id):
    from main import redis as r
    key = f"user:{id}:meters"
    
    # Получаем из Redis с await
    not_filled_str = await r.get(key)
    
    if not not_filled_str:
        not_filled = []
    else:
        not_filled = not_filled_str.split(',')
    
    buttons_row = []
    
    if 'hw' in not_filled:
        buttons_row.append(
            types.InlineKeyboardButton(text="🌡 Горячая вода", callback_data="selected_mr_hw_add")
        )
    
    if 'cw' in not_filled:
        buttons_row.append(
            types.InlineKeyboardButton(text="💧 Холодная вода", callback_data="selected_mr_cw_add")
        )
    
    if 'el' in not_filled:
        buttons_row.append(
            types.InlineKeyboardButton(text='⚡ Электричество', callback_data='enter_new_el_cb')
        )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[buttons_row])
    return keyboard

async def get_business_info(word,id):
    usname = await get_usname(id)
    file_path = 'docs/ГИРА_1006теккаа2.xlsx'
    df = pd.read_excel(file_path, sheet_name = 'Реестр')
    row = df.loc[df['ИНН'] == int(word)]
    
    
    
    # sheet = df2['реестр']
    # row2 = sheet.loc[df2['ИНН'] == int(word)]
    # excel_files = pd.ExcelFile(file_path)
    # sheets_name = excel_files.parse('реестр')
    # print(sheets_name)
    
    if not row.empty:
        name_company = row.iloc[0]['Арендатор']
        square_company = row.iloc[0]['Площадь']
        sheet_name_company = row.iloc[0]['Листы']
        acceptance_certificate = row.iloc[0]['Акт п/п']
        agreement_company = str(row.iloc[0]['Договор'])
        type_of_activity = str(row.iloc[0]['Вид деятельности']).strip().title()
        # bid = float(row.iloc[0]['Арендатор'])
        surname = str(row.iloc[0]['Фамилия'])
        first_name = str(row.iloc[0]['Имя'])
        patronymic = str(row.iloc[0]['Отчество'])
        form_of_doing = str(row.iloc[0]['Форма бизнеса'])
        end_date = str(row.iloc[0]['Срок аренды'])
        value = row.iloc[0]['Счет']
        bid = 0 if pd.isna(value) else float(value)
        square_company = float(square_company) if pd.notna(square_company) else 0.0
        print(f"Название компании: {name_company}")
        print(f"Площадь: {square_company}")
        print(f'Название листа: {sheet_name_company}')
        print(f"Акт приема-передачи: {acceptance_certificate}")
        print(f"Договор: {agreement_company}")
        check_types_in_db_record = await get_data('SELECT 0 <> COUNT(*) AS tofa FROM Type_of_Activity WHERE name = $1',type_of_activity)
        for result in check_types_in_db_record:
            check_toa_boolean = result['tofa']
        if check_toa_boolean == True:
            check_id_types_in_db_record = await get_data('SELECT id FROM Type_of_Activity WHERE name = $1',type_of_activity)
        else:
            await new_data_insert('INSERT INTO Type_of_Activity(name) VALUES ($1)', type_of_activity)
            check_id_types_in_db_record = await get_data('SELECT id FROM Type_of_Activity WHERE name = $1',type_of_activity)
        for result in check_id_types_in_db_record:
            id_toa = result['id']
        check_compny_in_db = await get_data('SELECT 0 <> COUNT(*) AS bool_check FROM Bussines WHERE name_company = $1', name_company)
        bool_check = [checkUserRecord['bool_check'] for checkUserRecord in check_compny_in_db]
        if bool_check[0]:
            new_obj = await get_data('SELECT * FROM Bussines WHERE Name_Company = $1', name_company)
        else:
            records_fod = await get_data('SELECT id FROM form_of_doing_business WHERE name = $1',form_of_doing)
            name_fods = [record['id'] for record in records_fod]
            if name_fods:  # если список не пустой
                name_fod = name_fods[0]
            else:
                # обработка случая, когда данные не найдены
                name_fod = None
            await new_data_insert('INSERT INTO Bussines(Name_Company, square, Acceptance_Certificate, Agreement, State_company, id_type_of_activity, surname, first_name, patronymic,end_date_agreement,sheet_name,id_form, bid) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)',name_company, square_company, acceptance_certificate, str(agreement_company), True, id_toa, surname, first_name, patronymic, end_date,sheet_name_company,name_fod, bid)
            new_obj = await get_data('SELECT * FROM Bussines WHERE Name_Company = $1',name_company)
        new_bisness_id_list =  [new_id['id'] for new_id in new_obj]
        new_bisness_id = int(new_bisness_id_list[0])
        await new_data_insert('INSERT INTO Users(User_Id,Id_Business,sheets_name,username) VALUES ($1,$2,$3,$4)',str(id),new_bisness_id,sheet_name_company,usname)
        print("Выполнили")
    else:
        print("Компания не найдена")
        return None, None

def get_type_business_keyboard():
    buttons = [
        [types.InlineKeyboardButton(text='ООО', callback_data='type_1_cb'),types.InlineKeyboardButton(text='ИП', callback_data='type_2_cb')],
        [types.InlineKeyboardButton(text='Самозанятость', callback_data='type_3_cb')],
        [types.InlineKeyboardButton(text='Товарищество', callback_data='type_4_cb')],
        [types.InlineKeyboardButton(text='Кооператив', callback_data='type_5_cb')],
        [types.InlineKeyboardButton(text='АО', callback_data='type_6_cb'),types.InlineKeyboardButton(text='ЗАО', callback_data='type_7_cb')]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons, resize_keyboard=True)
    return keyboard

@reg_router.message(RegStates.enterINN_state)
async def Check_INN(message: Message, state: FSMContext):
    try:
        await message.delete()
    except:
        pass
    from handlers.run import build_menu_keyboard, check_mr_for_user_in_db
    from main import redis as r
    inn_text = message.text
    id = message.chat.id
    check = check_word_in_excel_file(inn_text)
    if check:
        await get_business_info(inn_text,id)
        
        await state.set_state(Auth_States.menu_state)
        await message.answer('Вы в меню', reply_markup=await build_menu_keyboard(id))
        
    else:
        await message.answer('Не нашли вашу компанию, проверьте пожалуйста название и снова введите данные')

@reg_router.message(RegStates.enter_type_busines_state)
async def first_ask(message: types.Message, state: FSMContext):
    try:
        await message.delete()
    except:
        pass
    keyboard = get_type_business_keyboard()
    await message.answer('Пожалуйста выберите форму бизнеса', reply_markup=keyboard)

@reg_router.message(RegStates.enter_company_name_state)
async def second_ask(message: types.Message, state: FSMContext):
    try:
        await message.delete()
    except:
        pass
    from services.yandex_disk import check_yes_or_no_company
    name_company = message.text
    check = check_yes_or_no_company(name_company)
    if check and len(message.text)>3:
        await message.answer('Напишите пожалуйста ваше ФИО')
        await state.update_data(name_company = name_company)
        await state.set_state(RegStates.end_reg_state)
    else:
        await message.answer('Не нашли вашу компанию, проверьте пожалуйста название и снова введите данные')

@reg_router.message(RegStates.end_reg_state)
async def third_ask(message: types.Message, state: FSMContext):
    try:
        await message.delete()
    except:
        pass
    from handlers.run import build_menu_keyboard
    sfp = message.text
    id = message.chat.id
    second_name = sfp.split(' ')[0]
    first_name = sfp.split(' ')[1]
    patronymic = sfp.split(' ')[2]
    await state.set_state(Auth_States.menu_state)
    us_inf = await state.get_data()
    name_company = us_inf['name_company']
    form_id = us_inf['form_bus']
    check_compny_in_db = await get_data('SELECT 0 <> COUNT(*) AS bool_check FROM Bussines WHERE name_company = $1', name_company)
    bool_check = [checkUserRecord['bool_check'] for checkUserRecord in check_compny_in_db]
    if bool_check[0]: # Added safety check for empty companies
        new_obj = await get_data('SELECT * FROM Bussines WHERE Name_Company = $1',name_company)
    else:
        await new_data_insert('INSERT INTO Bussines(Name_Company, Id_form) VALUES ($1, $2)',name_company, form_id)
        new_obj = await get_data('SELECT * FROM Bussines WHERE Name_Company = $1',name_company)
    new_bisness_id_list =  [new_id['id'] for new_id in new_obj]
    new_bisness_id = int(new_bisness_id_list[0])
    await new_data_insert('INSERT INTO Users(User_Id,First_Name,Second_Name,Patronymic,Id_Business) VALUES ($1,$2,$3,$4,$5)',str(id),first_name,second_name,patronymic,new_bisness_id)
    await message.answer('Вы в меню', reply_markup=await build_menu_keyboard(id))

@reg_router.callback_query(F.data.in_(['type_1_cb','type_2_cb','type_3_cb','type_4_cb','type_5_cb','type_6_cb','type_7_cb']))
async def set_form_business(call: types.CallbackQuery, state: FSMContext):
    from main import redis
    user_id = call.from_user.id
    data = call.data
    await call.message.delete()
    id_form_business = int(data.split('_')[1])
    await state.update_data(form_bus = id_form_business)
    await call.message.answer('Записали форму бизнеса. Двигаемся дальше, как называется Ваша компания?')
    await state.set_state(RegStates.enter_company_name_state)