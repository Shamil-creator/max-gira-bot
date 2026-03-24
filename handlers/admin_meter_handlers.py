import re
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
import asyncpg
from handlers.config import config
from states.admin_states import AdminState
from handlers.admin_group import create_companies_keyboard
# Создаем отдельный роутер только для счетчиков
admin_meter_router = Router()

# Константы
MAX_METER_LENGTH = 25

# Временное хранилище (только на время сессии)
temp_meter_data = {}

async def new_data_insert(query: str, *params):
    try:
        conn = await asyncpg.connect(config.db_connection)
        result = await conn.execute(query,*params)
        return result
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

async def new_data_insert_many(query: str, params_list: list):
    """Пакетная вставка"""
    try:
        conn = await asyncpg.connect(config.db_connection)
        async with conn.transaction():
            # executemany ожидает список кортежей
            result = await conn.executemany(query, params_list)
        await conn.close()
        return result
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

def validate_meter_number(number: str) -> bool:
    """Проверка номера счетчика"""
    if len(number) > MAX_METER_LENGTH:
        return False
    return bool(re.match(r'^[a-zA-Zа-яА-Я0-9\-]+$', number))

def create_meter_keyboard(meter_data: dict, company_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для управления счетчиками"""
    builder = InlineKeyboardBuilder()
    
    # Холодная вода
    cold_text = f"✅ Холодная вода: {', '.join(meter_data['cold_water'])}" if meter_data['cold_water'] else "➕ Холодная вода"
    builder.row(InlineKeyboardButton(text=cold_text, callback_data=f"meter_cold_{company_id}"))
    
    # Горячая вода
    hot_text = f"✅ Горячая вода: {', '.join(meter_data['hot_water'])}" if meter_data['hot_water'] else "➕ Горячая вода"
    builder.row(InlineKeyboardButton(text=hot_text, callback_data=f"meter_hot_{company_id}"))
    
    # Электричество
    elec_text = f"✅ Электричество: {', '.join(meter_data['electricity'])}" if meter_data['electricity'] else "➕ Электричество"
    builder.row(InlineKeyboardButton(text=elec_text, callback_data=f"meter_elec_{company_id}"))
    
    # Кнопки действий
    builder.row(
        InlineKeyboardButton(text="💾 Сохранить", callback_data=f"meter_save_{company_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="meter_cancel")
    )
    
    return builder.as_markup()

@admin_meter_router.callback_query(F.data.startswith("fill_meters_"))
async def start_meter_filling(callback: CallbackQuery, state: FSMContext):
    """Начало заполнения счетчиков (вызывается после создания арендатора)"""
    company_id = int(callback.data.split("_")[2])
    
    # Сохраняем данные для возврата
    await state.update_data(
        company_id=company_id,
        return_message_id=callback.message.message_id,
        return_text=callback.message.text
    )
    
    # Кнопки выбора
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Я", callback_data="meter_filler_admin")],
        [InlineKeyboardButton(text="🏢 Арендатор", callback_data="meter_filler_tenant")],
    ])
    
    await callback.message.edit_text(
        "Кто заполнит номера счетчиков?",
        reply_markup=keyboard
    )
    await state.set_state(AdminState.meter_filler_choice)
    await callback.answer()

@admin_meter_router.callback_query(AdminState.meter_filler_choice, F.data == "meter_filler_tenant")
async def filler_tenant_chosen(callback: CallbackQuery, state: FSMContext):
    """Арендатор - возврат к компаниям"""
    data = await state.get_data()
    
    # Просто возвращаемся
    await callback.message.edit_text(
        text=data['return_text'],
        reply_markup=await create_companies_keyboard()
    )
    await state.clear()
    await callback.answer("✅ Арендатор сможет заполнить счетчики позже")

@admin_meter_router.callback_query(AdminState.meter_filler_choice, F.data == "meter_filler_admin")
async def filler_admin_chosen(callback: CallbackQuery, state: FSMContext):
    """Админ - начало ввода счетчиков"""
    data = await state.get_data()
    company_id = data['company_id']
    
    # Инициализируем данные
    temp_meter_data[company_id] = {
        'cold_water': [],
        'hot_water': [],
        'electricity': []
    }
    
    keyboard = create_meter_keyboard(temp_meter_data[company_id], company_id)
    
    await callback.message.edit_text(
        "🏭 <b>Ввод номеров счетчиков</b>\n\n"
        "Выберите тип счетчика для добавления:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )
    await state.set_state(AdminState.meter_type_selection)
    await callback.answer()

@admin_meter_router.callback_query(AdminState.meter_type_selection, F.data.startswith("meter_cold_"))
@admin_meter_router.callback_query(AdminState.meter_type_selection, F.data.startswith("meter_hot_"))
@admin_meter_router.callback_query(AdminState.meter_type_selection, F.data.startswith("meter_elec_"))
async def select_meter_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа счетчика для ввода"""
    meter_type = callback.data.split("_")[1]  # cold/hot/elec
    company_id = int(callback.data.split("_")[2])
    
    type_names = {
        'cold': 'холодной воды',
        'hot': 'горячей воды',
        'elec': 'электричества'
    }
    
    type_hints = {
        'cold': '❄️',
        'hot': '🔥',
        'elec': '⚡️'
    }
    
    await state.update_data(
        current_meter_type=meter_type,
        company_id=company_id
    )
    
    # Показываем текущие значения если есть
    meter_key = {'cold': 'cold_water', 'hot': 'hot_water', 'elec': 'electricity'}[meter_type]
    current = temp_meter_data[company_id].get(meter_key, [])
    current_text = f"\n📋 <b>Текущие номера:</b> {', '.join(current) if current else 'не заданы'}"
    
    await callback.message.edit_text(
        f"{type_hints[meter_type]} <b>Ввод номеров счетчика {type_names[meter_type]}</b>{current_text}\n\n"
        f"📝 Можно ввести несколько номеров через запятую\n"
        f"🔢 Разрешены: цифры, буквы (рус/лат) и дефис\n"
        f"📏 Максимум {MAX_METER_LENGTH} символов\n\n"
        "<i>Пример: 12345-AB, 67890-CD, 112233</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к списку", callback_data=f"meter_back_{company_id}")]
        ])
    )
    
    # Устанавливаем нужное состояние
    state_map = {
        'cold': AdminState.entering_cold_water,
        'hot': AdminState.entering_hot_water,
        'elec': AdminState.entering_electricity
    }
    await state.set_state(state_map[meter_type])
    await callback.answer()

@admin_meter_router.message(AdminState.entering_cold_water)
@admin_meter_router.message(AdminState.entering_hot_water)
@admin_meter_router.message(AdminState.entering_electricity)
async def process_meter_input(message: Message, state: FSMContext):
    """Обработка введенных номеров"""
    data = await state.get_data()
    company_id = data['company_id']
    meter_type = data['current_meter_type']
    
    meter_key = {
        'cold': 'cold_water',
        'hot': 'hot_water',
        'elec': 'electricity'
    }[meter_type]
    
    # Разбираем ввод
    numbers = [n.strip() for n in message.text.split(',') if n.strip()]
    
    valid = []
    invalid = []
    
    for num in numbers:
        if validate_meter_number(num):
            valid.append(num)
        else:
            invalid.append(num)
    
    if invalid:
        await message.answer(
            f"❌ <b>Некорректные номера:</b> {', '.join(invalid)}\n\n"
            f"✅ <b>Требования:</b>\n"
            f"• Только цифры, буквы и дефис\n"
            f"• Максимум {MAX_METER_LENGTH} символов\n\n"
            "Попробуйте снова:",
            parse_mode=ParseMode.HTML
        )
        return
    
    if not valid:
        await message.answer("❌ Введите хотя бы один номер")
        return
    
    # Сохраняем (заменяем, а не добавляем)
    temp_meter_data[company_id][meter_key] = valid
    
    type_names = {
        'cold': '❄️ Холодная вода',
        'hot': '🔥 Горячая вода',
        'elec': '⚡️ Электричество'
    }
    
    await message.answer(
        f"✅ <b>{type_names[meter_type]}</b>\n"
        f"Сохранены номера: {', '.join(valid)}",
        parse_mode=ParseMode.HTML
    )
    
    keyboard = create_meter_keyboard(temp_meter_data[company_id], company_id)
    
    await message.answer(
        "🏭 <b>Редактирование счетчиков</b>\n\n"
        "Выберите следующий тип или сохраните все:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )
    await state.set_state(AdminState.meter_type_selection)

@admin_meter_router.callback_query(F.data.startswith("meter_back_"))
async def back_to_meter_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню счетчиков"""
    data = await state.get_data()
    company_id = data['company_id']
    
    keyboard = create_meter_keyboard(temp_meter_data[company_id], company_id)
    
    await callback.message.edit_text(
        "🏭 <b>Редактирование счетчиков</b>\n\n"
        "Выберите тип счетчика:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )
    await state.set_state(AdminState.meter_type_selection)
    await callback.answer()

@admin_meter_router.callback_query(F.data.startswith("meter_save_"))
async def save_meters(callback: CallbackQuery, state: FSMContext):
    """Сохранение всех счетчиков"""
    company_id = int(callback.data.split("_")[2])
    data = await state.get_data()
    
    # 🔴 ЗДЕСЬ ВАШ КОД СОХРАНЕНИЯ В БД
    # await save_company_meters(company_id, temp_meter_data[company_id])

    # Показываем что сохранили
    
    meters = temp_meter_data[company_id]
    saved_text = []
    all_meters = []
    for meter in meters.get('cold_water', []):
        all_meters.append((meter, 1, company_id))
    for meter in meters.get('hot_water', []):
        all_meters.append((meter, 3, company_id))
    for meter in meters.get('electricity', []):
        all_meters.append((meter, 2, company_id))
    print(all_meters)
    if all_meters:
        await new_data_insert_many(
            'INSERT INTO us_readings(number_counter, counter_type_id, business_id) VALUES($1, $2, $3)',
            all_meters
        )
        saved_text.append(f"❄️ Холодная вода: {', '.join(meters['cold_water'])}")
        
    if meters['hot_water']:
        saved_text.append(f"🔥 Горячая вода: {', '.join(meters['hot_water'])}")
    if meters['electricity']:
        saved_text.append(f"⚡️ Электричество: {', '.join(meters['electricity'])}")
    
    # Очищаем временные данные
    if company_id in temp_meter_data:
        del temp_meter_data[company_id]
    
    # Возвращаемся к списку компаний
    await callback.message.edit_text(
        text=f"{data['return_text']}\n\n"
             f"✅ <b>Счетчики сохранены:</b>\n" + "\n".join(saved_text),
        reply_markup=await create_companies_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    await state.clear()
    await callback.answer("✅ Номера счетчиков сохранены!")

@admin_meter_router.callback_query(F.data == "meter_skip")
async def skip_meters(callback: CallbackQuery, state: FSMContext):
    """Пропустить добавление счетчиков"""
    data = await state.get_data()
    
    # Очищаем временные данные если есть
    if 'company_id' in data and data['company_id'] in temp_meter_data:
        del temp_meter_data[data['company_id']]
    
    # Возвращаемся
    await callback.message.edit_text(
        text=data['return_text'] + "\n\n⏭ <b>Счетчики пропущены</b>",
        reply_markup=await create_companies_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    await state.clear()
    await callback.answer("⏭ Пропущено")

@admin_meter_router.callback_query(F.data == "meter_cancel")
async def cancel_meter_input(callback: CallbackQuery, state: FSMContext):
    """Отмена всего процесса"""
    data = await state.get_data()
    
    # Очищаем временные данные
    if 'company_id' in data and data['company_id'] in temp_meter_data:
        del temp_meter_data[data['company_id']]
    
    # Возвращаемся
    await callback.message.edit_text(
        text=data['return_text'],
        reply_markup=await create_companies_keyboard()
    )
    
    await state.clear()
    await callback.answer("❌ Ввод отменен")