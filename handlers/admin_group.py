import locale
import os
from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters.command import Command
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types.input_file import FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
import logging
from datetime import date, datetime, timedelta
import asyncpg
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from typing import Dict, Any, Optional, Tuple, List
import re
from aiogram.exceptions import TelegramBadRequest
from handlers.config import config
from handlers.excel_tg_test import delete_in_excel,delete_sheet_in_excel
from states.admin_states import AdminState
from handlers.excel_tg_test import admin_indicators, create_excel, get_volume_and_amount_month, count_tenant_excel,create_word

admin_router = Router()

ADMIN_CHAT_ID = int(config.chanel_id.get_secret_value())
ADMIN_REGISTRATION_COMMAND = "/ГИРОАДМИН12409@hklz9(*bv"
SHEET_NAME = "ГИРА"
temp_documents = {}

file_lock = asyncio.Lock()

ALL_TYPES = ["electro", "water_cold", "expl", "drainage"]

# Функция для получения меток типов
def get_type_names():
    return {
        "electro": "электроэнергии",
        "water_cold": "холодной воды", 
        "expl": "коммунальных услуг",
        "drainage": "водоотведение"
    }

def get_type_labels():
    return {
        "electro": "⚡ Электроэнергия",
        "water_cold": "🚰 Холодная вода", 
        "expl": "🏢 Комм. услуги",
        "drainage": "💧 Водоотведение"
    }


def service_keyboard():
    """Клавиатура выбора услуги"""
    buttons = [
        [InlineKeyboardButton(text="🔥 Отопление", callback_data="service_heat")],
        [InlineKeyboardButton(text="📊 Общие показатели", callback_data="service_common")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_type_units():
    return {
        "electro": "электроэнергии (кВт·ч)",
        "water_cold": "холодной воды (м³)", 
        "expl": "коммунальных услуг",
        'drainage': 'водоотведение (руб)'
    }

# ===== УТИЛИТЫ =====

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
    
async def get_sheet_name_bs(id_comp):
    name = ''
    result_record = await get_data('SELECT sheet_name FROM bussines WHERE id = $1', id_comp)
    for result in result_record:
        name = result['sheet_name']
    return name 

async def new_data_insert(query: str, *params):
    conn = None
    try:
        conn = await asyncpg.connect(config.db_connection)
        result = await conn.execute(query, *params)
        return result
    except Exception as e:
        logging.error(f"Ошибка БД (new_data_insert): {e}")
        return None
    finally:
        if conn:
            await conn.close()

async def send_to_admin_topic(bot: Bot, text: str, reply_markup=None, parse_mode="Markdown"):
    """Отправить сообщение в единый админ-чат (без топиков)."""
    try:
        return await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"[АДМИН] {text}",
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception as e:
        logging.error(f"Ошибка отправки в админ-чат: {e}")
        return None

async def edit_admin_message(bot: Bot, message_id: int, text: str, reply_markup=None, parse_mode="Markdown"):
    """Редактировать сообщение в едином админ-чате."""
    try:
        await bot.edit_message_text(
            chat_id=ADMIN_CHAT_ID,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception as e:
        logging.error(f"Ошибка редактирования: {e}")


def _admin_access_key(user_id: int) -> str:
    return f"admin_access:{user_id}"


async def register_admin_access(user_id: int):
    from main import redis as r

    await r.set(_admin_access_key(user_id), "1")


async def has_admin_access(user_id: int) -> bool:
    from main import redis as r

    value = await r.get(_admin_access_key(user_id))
    return str(value) == "1"

# ===== КЛАВИАТУРЫ =====

def admin_main_keyboard():
    """Клавиатура главного меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Рассылка всем", callback_data="admin_broadcast_all")
    builder.button(text="👥 Выборочная рассылка", callback_data="admin_broadcast_select")
    builder.button(text="👤 Управление пользователями", callback_data="admin_manage_users")
    builder.button(text="📝 Подать показания", callback_data="admin_submit_readings")
    builder.button(text="🔄 Обновить",style="primary", callback_data="admin_refresh")
    builder.adjust(1)
    return builder.as_markup()

# def cancel_keyboard():
#     builder = InlineKeyboardBuilder()
#     builder.button(text="❌ Отмена", callback_data="admin_cancel")
#     return builder.as_markup()

def cancel_keyboard(with_edit_option=False):
    builder = InlineKeyboardBuilder()
    
    if with_edit_option:
        builder.button(text="🔙 Вернуться к редактированию", callback_data="admin_edit_menu")
    else:
        builder.button(text="❌ Отмена", callback_data="admin_cancel")
    
    return builder.as_markup()

def confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data="admin_confirm_send")
    builder.button(text="✏️ Редактировать", callback_data="admin_edit_message")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(2, 1)
    return builder.as_markup()

def users_selection_keyboard(users_data, selected_ids, page=0):
    """
    Клавиатура выбора пользователей с пагинацией
    users_data: список словарей [{'user_id': 123, 'name_company': 'Название', 'display_name': 'Отображаемое имя'}]
    selected_ids: список выбранных user_id
    page: номер страницы
    """
    builder = InlineKeyboardBuilder()
    
    users_per_page = 8  # Уменьшил чтобы больше помещалось
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    page_users = users_data[start_idx:end_idx]
    
    # Кнопки пользователей - отображаем название компании
    for user in page_users:
        user_id = user['user_id']
        company_name = user.get('name_company', '')
        
        # Форматируем название компании
        display_name = company_name or f"ID: {user_id}"
        if len(display_name) > 18:
            display_name = display_name[:16] + "..."
        
        # Приводим к строке для корректного сравнения
        u_id_str = str(user_id)
        mark = "✅" if u_id_str in [str(sid) for sid in selected_ids] else "⬜"
        builder.button(
            text=f"{mark} {display_name}",
            callback_data=f"admin_toggle_{u_id_str}"
        )
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(("⬅️ Назад", f"admin_page_{page-1}"))
    
    # Информация о странице
    total_pages = (len(users_data) + users_per_page - 1) // users_per_page
    nav_buttons.append((f"{page+1}/{total_pages}", "noop"))
    
    if end_idx < len(users_data):
        nav_buttons.append(("Вперед ➡️", f"admin_page_{page+1}"))
    
    # Добавляем кнопки навигации
    for text, data in nav_buttons:
        builder.button(text=text, callback_data=data)
    
    # Управляющие кнопки (перенесем их в отдельный ряд)
    builder.button(text="✅ Выбрать всех", callback_data="admin_select_all")
    builder.button(text="❌ Снять всех", callback_data="admin_deselect_all")
    
    builder.button(text="🚀 Продолжить", callback_data="admin_continue_selection")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    
    # Распределение кнопок:
    # 1. Пользователи по 2 в ряд
    # 2. Навигация в отдельном ряду
    # 3. Управляющие кнопки по 2 в ряд
    builder.adjust(2, 2, 2, 2, len(nav_buttons), 2, 2)
    
    return builder.as_markup()

def get_edit_keyboard():
    builder = InlineKeyboardBuilder()
    
    # Кнопки для редактирования каждого типа
    builder.button(text="⚡ Редактировать электричество", callback_data="admin_edit_electro")
    builder.button(text="🚰 Редактировать холодную воду", callback_data="admin_edit_water_cold")
    builder.button(text='💧 Редактировать тариф водоотведения', callback_data='admin_edit_drainage')
    builder.button(text="🏢 Комм. услуги", callback_data="admin_edit_expl")
    
    # Кнопки действий
    builder.button(text="💾 Сохранить все показания",style="success", callback_data="admin_save_all")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1)
    
    return builder.as_markup()

def type_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡ Электроэнергия", callback_data="admin_type_electro")
    builder.button(text="🚰 Холодная вода", callback_data="admin_type_water_cold")
    builder.button(text='💧 Водоотведение', callback_data='admin_type_drainage')
    # builder.button(text="🌡 Отопление", callback_data="admin_type_heat")
    builder.button(text="🏢 Коммунальные услуги", callback_data="admin_type_expl")  # Добавили
    builder.button(text="🔙 Назад", callback_data="admin_to_main")
    builder.adjust(1)
    return builder.as_markup()

def method_keyboard():
    """Клавиатура выбора способа подачи"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⌨️ Ввести вручную", callback_data="admin_method_manual")
    builder.button(text="📄 Отправить файл (PDF)", callback_data="admin_method_pdf")
    builder.button(text="🔙 Назад", callback_data="admin_submit_readings_back")
    builder.adjust(1)
    return builder.as_markup()

def submission_cancel_keyboard():
    """Клавиатура отмены для подачи показаний"""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена подачи", callback_data="admin_to_main")
    return builder.as_markup()

def check_word_in_excel_file(word):
    import pandas as pd
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

# ===== ОБРАБОТЧИКИ КОМАНД =====

@admin_router.message(F.text == ADMIN_REGISTRATION_COMMAND)
async def admin_register(message: Message, state: FSMContext):
    await register_admin_access(message.from_user.id)
    await state.clear()
    await message.answer("✅ Админ-доступ активирован для этого аккаунта.")
    try:
        await message.delete()
    except Exception:
        pass

@admin_router.message(Command("admin"))
async def admin_login(message: Message, state: FSMContext, bot: Bot):   
    global ADMIN_CHAT_ID
    global collected_data

    if not await has_admin_access(message.from_user.id):
        await message.answer("⛔ Доступ запрещен. Сначала отправьте секретную команду регистрации.")
        return

    # Админ-панель работает в текущем чате, где выполнен /admin.
    ADMIN_CHAT_ID = message.chat.id
    collected_data = {}  # Сбрасываем предыдущие данные
    await state.clear()
    
    count_query = "SELECT COUNT(*) as count FROM users"
    count_result = await get_data(count_query)
    total_users = count_result[0]['count'] if count_result else 0
    
    # Отправляем панель в админ-топик
    admin_message = await send_to_admin_topic(
        bot,
        f"🔐 Административная панель\n\n"
        f"👥 Пользователей: {total_users}\n\n"
        "Выберите действие:",
        reply_markup=admin_main_keyboard(),
        parse_mode="HTML"
    )
    
    if admin_message:
        await state.update_data(admin_message_id=admin_message.message_id)
        await state.set_state(AdminState.admin_menu)
    
    try:
        await message.delete()
    except:
        pass


# Храним собранные данные
collected_data = {}
unexpected_expenses = 0.0

@admin_router.callback_query(F.data == "admin_submit_readings_back", StateFilter(AdminState.admin_menu))
async def admin_submit_readings(call: CallbackQuery, state: FSMContext, bot: Bot):
    query = "SELECT COUNT(*) as count FROM users"
    result = await get_data(query)
    total_users = result[0]['count'] if result else 0
    
    await state.set_state(AdminState.admin_menu)
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"🔐 Административная панель\n\n"
        f"👥 Пользователей: {total_users}\n\n"
        "Выберите действие:",
        reply_markup=admin_main_keyboard()
    )
    await call.answer()

# @admin_router.callback_query(F.data == "admin_submit_readings", StateFilter(AdminState.admin_menu))
# async def admin_submit_readings(call: CallbackQuery, state: FSMContext, bot: Bot):
#     """Начало подачи показаний - сбрасываем данные"""
#     global collected_data
#     collected_data = {}  # Сбрасываем предыдущие данные
    
#     await state.set_state(AdminState.choosing_type)
#     await edit_admin_message(
#         bot,
#         call.message.message_id,
#         "📊 Подача показаний\n\n"
#         "Выберите тип показаний для внесения:",
#         reply_markup=type_keyboard(),
#         parse_mode="HTML"
#     )
#     await call.answer()

@admin_router.callback_query(F.data.startswith("admin_type_"), StateFilter(AdminState.choosing_type))
async def admin_process_type(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора типа показаний"""
    kind = call.data.split("_")[2:]  # ['admin', 'type', 'electro'] -> ['electro']
    kind = "_".join(kind)  # 'electro' или 'water_cold' или 'water_hot' или 'heat' или 'expl'
    
    # Сохраняем текущий тип в состоянии
    await state.update_data(current_type=kind)
    
    # Для эксплуатационных услуг сразу переходим к вводу суммы
    if kind == "expl":
        await state.update_data(step="amount")
        await state.set_state(AdminState.waiting_for_amount_expl) 
    elif kind == 'drainage':
        await state.update_data(state='amount')
        await state.set_state(AdminState.waiting_for_amount_drainage)
    elif kind == 'water_cold':  # Для холодной воды - только тариф
        await state.update_data(step="tariff")
        await state.set_state(AdminState.waiting_for_tariff)
    else:
        await state.set_state(AdminState.choosing_method)
    
    names = get_type_names()
    label = names.get(kind, "показаний")

    if kind == "expl":
        await edit_admin_message(
            bot,
            call.message.message_id,
            f"📊 Подача показаний {label}\n\n"
            f"Введите сумму с НДС для {label} (в рублях):\n"
            f"(например: 1250.75)",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
    elif kind == 'drainage':
        await edit_admin_message(
            bot,
            call.message.message_id,
            f"📊 Подача показаний {label}\n\n"
            f"Введите ставку для {label} (в рублях):\n"
            f"(например: 12.75)",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
    elif kind == 'water_cold':
        await edit_admin_message(
            bot,
            call.message.message_id,
            f"📊 Подача показаний {label}\n\n"
            f"Введите тариф для {label} (в рублях за м³):\n"
            f"(например: 45.50)",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
    else:
        await edit_admin_message(
            bot,
            call.message.message_id,
            f"📊 Подача показаний {label}\n\n"
            f"Как вы хотите передать данные?",
            reply_markup=method_keyboard(),
            parse_mode="HTML"
        )
    await call.answer()

@admin_router.message(StateFilter(AdminState.waiting_for_tariff))
async def process_tariff_input(message: Message, state: FSMContext, bot: Bot):
    """Обработка введенного тарифа для холодной воды"""
    try:
        await message.delete()
    except:
        pass
    if message.chat.id != ADMIN_CHAT_ID:
        return
    
    raw_text = message.text.replace(",", ".")
    
    try:
        tariff = float(raw_text)
        if tariff < 0:
            raise ValueError
    except ValueError:
        await send_to_admin_topic(
            bot,
            "⚠️ Ошибка ввода\n\n"
            "Пожалуйста, введите корректный тариф (положительное число).",
            reply_markup=cancel_keyboard()
        )
        return
    
    data = await state.get_data()
    current_type = data.get("current_type")  # Должно быть "water_cold"
    
    # Сохраняем тариф
    global collected_data
    if current_type not in collected_data:
        collected_data[current_type] = {}
    
    collected_data[current_type]["tariff"] = tariff
    
    names = get_type_labels()
    label = names.get(current_type, "")
    
    # Проверяем, все ли типы заполнены
    missing_types_for_users = []
    collected_types = list(collected_data.keys())
    
    # Проверяем, какие типы из ALL_TYPES отсутствуют
    missing_types = [t for t in ALL_TYPES if t not in collected_types]
    
    # Преобразуем в читаемые названия
    type_to_readable = {
        'electro': 'электричество',
        'water_cold': 'холодная вода',
        'expl': 'коммунальные услуги',
        'drainage': 'водоотведение'
    }
    
    for type_miss in missing_types:
        missing_types_for_users.append(type_to_readable.get(type_miss, type_miss))
    
    builder = InlineKeyboardBuilder()
    
    if missing_types:
        builder.button(text="📝 Добавить следующий показатель", callback_data="admin_add_next")
    else:
        builder.button(text="✏️ Редактировать показания", callback_data="admin_edit_menu")
        # Добавляем кнопку для непредвиденных расходов
        builder.button(text="💰 Непредвиденные расходы", callback_data="admin_unexpected_expenses")
        builder.button(text="💾 Сохранить все показания", style="success", callback_data="admin_save_all")
    
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1)
    
    await send_to_admin_topic(
        bot,
        f"✅ Данные сохранены:\n\n"
        f"{label}\n"
        f"• Тариф: {tariff} руб./м³\n\n"
        f"Собрано показаний: {len(collected_types)} из 5\n\n"
        f"{'📋 Все показатели собраны!' if not missing_types else '📝 Осталось заполнить: ' + ', '.join(missing_types_for_users)}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    
    await state.set_state(AdminState.collecting_data)
    
    try:
        await bot.delete_message(ADMIN_CHAT_ID, message.message_id)
    except:
        pass

# @admin_router.callback_query(F.data == "admin_unexpected_expenses", StateFilter(AdminState.collecting_data))
# async def unexpected_expenses_handler(call: CallbackQuery, state: FSMContext, bot: Bot):
#     """Запрос суммы непредвиденных расходов"""
#     print(f'Зашли в admin_unexpected_expenses')
#     await state.set_state(AdminState.waiting_for_unexpected)
    
#     await edit_admin_message(
#         bot,
#         call.message.message_id,
#         "💰 <b>Непредвиденные расходы</b>\n\n"
#         "Введите сумму непредвиденных расходов (в рублях):\n"
#         "(например: 1500.00)\n\n"
#         "<i>Эти расходы будут добавлены к общей сумме</i>",
#         reply_markup=cancel_keyboard(),
#         parse_mode=ParseMode.HTML
#     )
#     await call.answer()

@admin_router.callback_query(F.data == "admin_unexpected_expenses", StateFilter(AdminState.collecting_data))
async def unexpected_expenses_handler(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Запрос суммы непредвиденных расходов"""
    print(f'Зашли в admin_unexpected_expenses')
    
    # СОХРАНЯЕМ ID исходного сообщения (которое будем редактировать потом)
    original_message_id = call.message.message_id
    
    # ОТПРАВЛЯЕМ сообщение с запросом суммы и СОХРАНЯЕМ его ID
    prompt_message = await bot.send_message(
        chat_id=call.message.chat.id,
        text="💰 <b>Введите сумму непредвиденных расходов</b>\n\n"
             "(например: 1500.00)\n\n"
             "<i>Эти расходы будут добавлены к общей сумме</i>",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    
    # Сохраняем оба ID в состоянии
    await state.set_state(AdminState.waiting_for_unexpected)
    await state.update_data(
        original_message_id=original_message_id,
        prompt_message_id=prompt_message.message_id  # <-- ВАЖНО!
    )
    
    await call.answer()

# @admin_router.message(StateFilter(AdminState.waiting_for_unexpected))
# async def process_unexpected_amount(message: Message, state: FSMContext, bot: Bot):
#     """Обработка введенной суммы непредвиденных расходов"""
#     if message.chat.id != ADMIN_CHAT_ID:
#         return
    
#     raw_text = message.text.replace(",", ".")
    
#     try:
#         amount = float(raw_text)
#         if amount < 0:
#             raise ValueError
#     except ValueError:
#         await send_to_admin_topic(
#             bot,
#             "⚠️ Ошибка ввода\n\n"
#             "Пожалуйста, введите корректную сумму (положительное число).",
#             reply_markup=cancel_keyboard()
#         )
#         return
    
#     # Сохраняем сумму в состоянии
#     await state.update_data(unexpected_expenses=amount)
    
#     # Возвращаемся в меню выбора
#     await state.set_state(AdminState.collecting_data)
    
#     # Получаем данные для отчета
#     global collected_data
#     data = await state.get_data()
#     unexpected = data.get("unexpected_expenses", 0)
    
#     # Формируем отчет со всеми показателями
#     report = "💰 <b>Непредвиденные расходы добавлены!</b>\n\n"
#     report += f"Сумма: {amount} руб.\n\n"
#     report += "📊 <b>Все показатели:</b>\n\n"
    
#     # Отопление
#     if 'heating' in collected_data:
#         report += f"🔥 Отопление: {collected_data['heating'].get('amount', 0)} руб.\n"
    
#     # Остальные показатели
#     names = {
#         'electro': '⚡ Электроэнергия',
#         'water_cold': '🚰 Холодная вода',
#         'expl': '🏢 Комм. услуги',
#         'drainage': '💧 Водоотведение'
#     }
    
#     for key, label in names.items():
#         if key in collected_data:
#             data_item = collected_data[key]
#             if key == 'water_cold':
#                 report += f"{label}: {data_item.get('tariff', 0)} руб./м³\n"
#             else:
#                 report += f"{label}: {data_item.get('amount', 0)} руб.\n"
    
#     if unexpected > 0:
#         report += f"\n💰 <b>Непредвиденные расходы:</b> {unexpected} руб."
    
#     # Кнопки для дальнейших действий
#     builder = InlineKeyboardBuilder()
#     builder.button(text="💰 Изменить расходы", callback_data="admin_unexpected_expenses")
#     builder.button(text="📎 Прикрепить документы", callback_data="admin_attach_documents")
#     builder.button(text="✅ Отправить", callback_data="admin_final_save")
#     builder.button(text="❌ Отмена", callback_data="admin_cancel")
#     builder.adjust(1)
    
#     # Получаем ID последнего сообщения для редактирования
#     state_data = await state.get_data()
#     last_msg_id = state_data.get("last_msg_id")
    
#     if last_msg_id:
#         try:
#             await bot.edit_message_text(
#                 chat_id=ADMIN_CHAT_ID,
#                 message_id=last_msg_id,
#                 text=report,
#                 reply_markup=builder.as_markup(),
#                 parse_mode=ParseMode.HTML
#             )
#         except Exception as e:
#             print(f"Ошибка редактирования: {e}")
#             new_msg = await bot.send_message(
#                 chat_id=ADMIN_CHAT_ID,
#                 text=report,
#                 reply_markup=builder.as_markup(),
#                 parse_mode=ParseMode.HTML
#             )
#             await state.update_data(last_msg_id=new_msg.message_id)
#     else:
#         new_msg = await bot.send_message(
#             chat_id=ADMIN_CHAT_ID,
#             text=report,
#             reply_markup=builder.as_markup(),
#             parse_mode=ParseMode.HTML
#         )
#         await state.update_data(last_msg_id=new_msg.message_id)
    
#     # Удаляем сообщение с вводом
#     try:
#         await bot.delete_message(ADMIN_CHAT_ID, message.message_id)
#     except:
#         pass


@admin_router.message(StateFilter(AdminState.waiting_for_unexpected))
async def process_unexpected_amount(message: Message, state: FSMContext, bot: Bot):
    """Обработка введенной суммы непредвиденных расходов"""
    # 1. Сразу пытаемся удалить сообщение пользователя для чистоты чата
    try:
        await bot.delete_message(message.chat.id, message.message_id)
        logging.info(f"Удалено сообщение пользователя {message.message_id}")
    except Exception as e:
        logging.error(f"Не удалось удалить сообщение пользователя: {e}")

    # 2. Проверяем права доступа по пользователю, а не по ID чата
    if not await has_admin_access(message.from_user.id):
        return
    
    raw_text = message.text.replace(",", ".")
    try:
        amount = float(raw_text)
        if amount < 0:
            raise ValueError
    except ValueError:
        await send_to_admin_topic(
            bot,
            "⚠️ Ошибка ввода\n\n"
            "Пожалуйста, введите корректную сумму (положительное число).",
            reply_markup=cancel_keyboard()
        )
        return
    
    # Сохраняем сумму в состоянии
    await state.update_data(unexpected_expenses=amount)
    
    # Получаем сохраненные ID сообщений
    state_data = await state.get_data()
    original_message_id = state_data.get("original_message_id")
    prompt_message_id = state_data.get("prompt_message_id")
    
    # УДАЛЯЕМ сообщение с запросом (которое бот отправил ранее)
    if prompt_message_id:
        try:
            await bot.delete_message(message.chat.id, prompt_message_id)
        except Exception as e:
            logging.error(f"Не удалось удалить приглашение: {e}")
    
    # Возвращаемся в меню выбора
    await state.set_state(AdminState.collecting_data)
    
    # Получаем данные для отчета
    global collected_data
    data = await state.get_data()
    unexpected = data.get("unexpected_expenses", 0)
    
    # Формируем отчет
    report = "💰 <b>Непредвиденные расходы добавлены!</b>\n\n"
    report += f"Сумма: {amount} руб.\n\n"
    report += "📊 <b>Все показатели:</b>\n\n"
    
    # Отопление
    if 'heating' in collected_data:
        report += f"🔥 Отопление: {collected_data['heating'].get('amount', 0)} руб.\n"
    
    # Остальные показатели
    names = {
        'electro': '⚡ Электроэнергия',
        'water_cold': '🚰 Холодная вода',
        'expl': '🏢 Комм. услуги',
        'drainage': '💧 Водоотведение'
    }
    
    for key, label in names.items():
        if key in collected_data:
            data_item = collected_data[key]
            if key == 'water_cold':
                report += f"{label}: {data_item.get('tariff', 0)} руб./м³\n"
            else:
                report += f"{label}: {data_item.get('amount', 0)} руб.\n"
    
    if unexpected > 0:
        report += f"\n💰 <b>Непредвиденные расходы:</b> {unexpected} руб."
    
    # Кнопки для дальнейших действий
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Изменить расходы", callback_data="admin_unexpected_expenses")
    builder.button(text="📎 Прикрепить документы", callback_data="admin_attach_documents")
    builder.button(text="✅ Отправить", callback_data="admin_final_save")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1)
    
    # Отправляем НОВОЕ сообщение с отчетом (чтобы оно было внизу чата)
    try:
        new_msg = await bot.send_message(
            chat_id=message.chat.id,
            text=report,
            reply_markup=builder.as_markup(),
            parse_mode=ParseMode.HTML
        )
        # Сохраняем ID нового сообщения как последнее активное
        await state.update_data(last_msg_id=new_msg.message_id)
        logging.info(f"Отправлен новый отчет по расходам: {new_msg.message_id}")
    except Exception as e:
        logging.error(f"Ошибка отправки нового отчета: {e}")

@admin_router.callback_query(F.data == "add_document_unexpected", StateFilter(AdminState.collecting_data))
async def add_unexpected_docs(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Добавление документов к непредвиденным расходам"""
    # Инициализируем хранилище документов для непредвиденных расходов
    data = await state.get_data()
    business_id = data.get('business_id', 'unexpected')
    
    temp_documents['unexpected'] = {
        'files': [],
        'message_id': call.message.message_id,
        'chat_id': call.message.chat.id
    }
    await state.update_data(business_id='unexpected', doc_type='unexpected')
    
    await state.set_state(AdminState.waiting_for_documents_unexpected)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        "📎 <b>Подтверждающие документы для непредвиденных расходов</b>\n\n"
        "Прикрепите подтверждающие документы (счета, акты, накладные).\n",
        reply_markup=create_document_keyboard_unexpected(has_files=False),
        parse_mode=ParseMode.HTML
    )
    await call.answer()

# Обработчик для пропуска документов по непредвиденным расходам
@admin_router.callback_query(F.data == "proceed_without_docs_unexpected", StateFilter(AdminState.collecting_data))
async def proceed_without_docs_unexpected(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Пропуск документов для непредвиденных расходов"""
    await proceed_with_sending_unexpected(call, state, documents=[])


@admin_router.message(AdminState.confirming_documents_unexpected, F.document)
async def process_unexpected_document(message: Message, state: FSMContext, bot: Bot):
    """Обработка полученного документа для непредвиденных расходов"""
    if 'unexpected' not in temp_documents:
        temp_documents['unexpected'] = {'files': []}
    
    doc = message.document
    temp_documents['unexpected']['files'].append({
        'file_id': doc.file_id,
        'file_name': doc.file_name,
        'file_size': doc.file_size,
        'mime_type': doc.mime_type
    })
    
    file_list = get_file_list_text(temp_documents['unexpected']['files'])
    await message.answer(
        f"✅ <b>Файл добавлен!</b>\n\n<b>Загруженные файлы (непредвиденные расходы):</b>\n{file_list}\n\nМожете добавить еще или отправить.",
        reply_markup=create_document_keyboard_unexpected(has_files=True),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.waiting_for_documents_unexpected)

@admin_router.message(AdminState.confirming_documents_unexpected, F.photo)
async def process_unexpected_photo(message: Message, state: FSMContext, bot: Bot):
    """Обработка фото для непредвиденных расходов"""
    if 'unexpected' not in temp_documents:
        temp_documents['unexpected'] = {'files': []}
    
    photo = message.photo[-1]
    temp_documents['unexpected']['files'].append({
        'file_id': photo.file_id,
        'file_name': f"photo_{datetime.now().strftime('%H%M%S')}.jpg",
        'file_size': photo.file_size,
        'mime_type': 'image/jpeg'
    })
    
    file_list = get_file_list_text(temp_documents['unexpected']['files'])
    await message.answer(
        f"✅ <b>Фото добавлено!</b>\n\n<b>Загруженные файлы (непредвиденные расходы):</b>\n{file_list}\n\nМожете добавить еще или отправить.",
        reply_markup=create_document_keyboard_unexpected(has_files=True),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.waiting_for_documents_unexpected)

@admin_router.message(AdminState.confirming_documents_unexpected, F.photo)
async def process_unexpected_photo(message: Message, state: FSMContext, bot: Bot):
    """Обработка полученного фото для непредвиденных расходов"""
    if 'unexpected' not in temp_documents:
        temp_documents['unexpected'] = {'files': []}
    
    photo = message.photo[-1]
    file_info = {
        'file_id': photo.file_id,
        'file_name': f"photo_unexpected_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
        'file_size': photo.file_size,
        'mime_type': 'image/jpeg'
    }
    
    temp_documents['unexpected']['files'].append(file_info)
    
    file_list = "\n".join([f"🖼️ {f['file_name']}" for f in temp_documents['unexpected']['files']])
    
    await message.answer(
        f"✅ <b>Фото добавлено!</b>\n\n"
        f"<b>Загруженные файлы (непредвиденные расходы):</b>\n{file_list}\n\n"
        f"Можете добавить еще или отправить.",
        reply_markup=create_document_keyboard_unexpected(has_files=True),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.waiting_for_documents_unexpected)

@admin_router.callback_query(F.data == "add_more_docs_unexpected", AdminState.waiting_for_documents_unexpected)
async def add_more_unexpected_docs(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Добавление еще документов для непредвиденных расходов"""
    await add_unexpected_document_prompt(call, state, bot)

@admin_router.callback_query(F.data == "back_to_docs_menu_unexpected", AdminState.confirming_documents_unexpected)
async def back_to_unexpected_docs_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Возврат в меню документов непредвиденных расходов"""
    await state.set_state(AdminState.waiting_for_documents_unexpected)
    
    if 'unexpected' in temp_documents and temp_documents['unexpected']['files']:
        file_list = "\n".join([f"📄 {f['file_name']}" for f in temp_documents['unexpected']['files']])
        text = f"📎 <b>Подтверждающие документы (непредвиденные расходы)</b>\n\n<b>Загруженные файлы:</b>\n{file_list}"
    else:
        text = "📎 <b>Подтверждающие документы (непредвиденные расходы)</b>\n\nПрикрепите подтверждающие документы."
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        text,
        reply_markup=create_document_keyboard_unexpected(has_files=bool(temp_documents.get('unexpected', {}).get('files'))),
        parse_mode=ParseMode.HTML
    )
    await call.answer()

@admin_router.callback_query(F.data == "skip_documents_unexpected")
async def skip_unexpected_documents(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Отправить без документов (непредвиденные расходы)"""
    await proceed_with_sending_unexpected(call, state, documents=[])

@admin_router.callback_query(F.data == "send_with_docs_unexpected")
async def send_with_unexpected_documents(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Отправить с документами (непредвиденные расходы)"""
    documents = temp_documents.get('unexpected', {}).get('files', [])
    await proceed_with_sending_unexpected(call, state, documents)

@admin_router.callback_query(F.data == "cancel_docs_unexpected")
async def cancel_unexpected_documents(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Отмена отправки (непредвиденные расходы)"""
    if 'unexpected' in temp_documents:
        del temp_documents['unexpected']
    
    await state.set_state(AdminState.collecting_data)
    
    # Возвращаемся к меню сбора данных
    names = get_type_labels()
    collected_types = list(collected_data.keys())
    missing_types = [t for t in ALL_TYPES if t not in collected_types]
    
    type_to_readable = {
        'electro': 'электричество',
        'water_cold': 'холодная вода',
        'expl': 'коммунальные услуги',
        'drainage': 'водоотведение'
    }
    
    missing_types_for_users = [type_to_readable.get(t, t) for t in missing_types]
    
    builder = InlineKeyboardBuilder()
    
    if missing_types:
        builder.button(text="📝 Добавить следующий показатель", callback_data="admin_add_next")
    else:
        builder.button(text="✏️ Редактировать показания", callback_data="admin_edit_menu")
        builder.button(text="💰 Непредвиденные расходы", callback_data="admin_unexpected_expenses")
        builder.button(text="💾 Сохранить все показания", style="success", callback_data="admin_save_all")
    
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1)
    
    report = f"✅ Данные сохранены\n\nСобрано показаний: {len(collected_types)} из 5\n\n"
    if not missing_types:
        report += "📋 Все показатели собраны!\n"
    else:
        report += f"📝 Осталось заполнить: {', '.join(missing_types_for_users)}"
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        report,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await call.answer()

async def proceed_with_sending_unexpected(call: CallbackQuery, state: FSMContext, documents: list):
    """Финальная отправка с непредвиденными расходами"""
    from main import bot
    
    data = await state.get_data()
    global unexpected_expenses
    
    # Анимация загрузки
    stages = [
        (10, "🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Подготовка данных..."),
        (20, "🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Сохранение показателей..."),
        (30, "🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Получение списка пользователей..."),
        (40, "🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️", "Формирование отчетов..."),
        (50, "🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️", "Создание Excel файлов..."),
        (60, "🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️", "Отправка документов..."),
        (70, "🟩🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️", "Отправка уведомлений..."),
        (80, "🟩🟩🟩🟩🟩🟩🟩🟩⬛️⬛️", "Формирование отчета..."),
        (90, "🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛️", "Завершение процесса..."),
        (100, "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩", "✅ Готово!")
    ]
    
    # Шаг 1 - подготовка
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔄 <b>Отправка данных...</b>\n\n"
             f"{stages[0][1]} {stages[0][0]}%\n\n"
             f"{stages[0][2]}",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.5)
    
    # Подготовка периода
    start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%d.%m.%Y")
    end = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%d.%m.%Y")
    prev = datetime.now().replace(day=1) - timedelta(days=1)
    months_ru = {
                1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
                5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
                9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
            }
    prev = datetime.now().replace(day=1) - timedelta(days=1)
    period_str = f"{months_ru[prev.month]} {prev.year}"
    info_list = [end,start,end,period_str]

    
    # Шаг 2 - сохранение показателей
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔄 <b>Отправка данных...</b>\n\n"
             f"{stages[1][1]} {stages[1][0]}%\n\n"
             f"{stages[1][2]}",
        parse_mode=ParseMode.HTML
    )
    await admin_indicators(collected_data)
    await asyncio.sleep(0.3)
    
    # Шаг 3 - получение списка пользователей
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔄 <b>Отправка данных...</b>\n\n"
             f"{stages[2][1]} {stages[2][0]}%\n\n"
             f"{stages[2][2]}",
        parse_mode=ParseMode.HTML
    )
    
    all_users = await get_data('SELECT User_Id as user_id FROM users')
    list_users = [user['user_id'] for user in all_users]
    count_users = await count_tenant_excel()
    await asyncio.sleep(0.3)
    
    # Шаги 4-7 - отправка пользователям
    total_users = len(list_users)
    for idx, user in enumerate(list_users):
        progress = 40 + int((idx / total_users) * 40) if total_users > 0 else 60
        
        if progress < 50:
            indicator = "🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️"
        elif progress < 60:
            indicator = "🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️"
        elif progress < 70:
            indicator = "🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️"
        elif progress < 80:
            indicator = "🟩🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️"
        else:
            indicator = "🟩🟩🟩🟩🟩🟩🟩🟩⬛️⬛️"
        
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🔄 <b>Отправка данных...</b>\n\n"
                 f"{indicator} {progress}%\n\n"
                 f"Отправка пользователю {idx+1}/{total_users}...",
            parse_mode=ParseMode.HTML
        )

        # text_for_user = await get_volume_and_amount_month(user)
        file = await create_word(collected_data, user, count_users, info_list, unexpected_expenses)
        document = FSInputFile(file)
        
        caption = '🧾 Ваш счёт за прошедший месяц'
        if unexpected_expenses > 0:
            caption += f'\n\n💰 Непредвиденные расходы: {unexpected_expenses} руб.'
        
        await bot.send_document(
            chat_id=int(user),
            document=document,
            caption=caption
        )
        os.unlink(file)
        
        # Отправляем приложенные документы (непредвиденные расходы)
        for doc in documents:
            mime = (doc.get('mime_type') or "").lower()
            file_id = doc.get('file_id')
            file_name = doc.get('file_name', 'Документ')
            
            if "image" in mime or file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                await bot.send_photo(
                    chat_id=int(user),
                    photo=file_id,
                    caption=f"📸 Подтверждающее фото (расходы)"
                )
            elif "video" in mime or file_name.lower().endswith(('.mp4', '.mov', '.avi')):
                await bot.send_video(
                    chat_id=int(user),
                    video=file_id,
                    caption=f"🎬 Подтверждающее видео (расходы)"
                )
            else:
                await bot.send_document(
                    chat_id=int(user),
                    document=file_id,
                    caption=f"📎 Подтверждающий документ (расходы): {file_name}"
                )
        
        # await bot.send_message(chat_id=int(user), text=text_for_user)
        await asyncio.sleep(0.2)
    
    # Шаг 8 - формирование отчета
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔄 <b>Отправка данных...</b>\n\n"
             f"{stages[7][1]} {stages[7][0]}%\n\n"
             f"{stages[7][2]}",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.3)
    
    # Шаг 9 - завершение
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔄 <b>Отправка данных...</b>\n\n"
             f"{stages[8][1]} {stages[8][0]}%\n\n"
             f"{stages[8][2]}",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.3)
    
    # Очищаем временные данные
    if 'unexpected' in temp_documents:
        del temp_documents['unexpected']
    
    # Финальный отчет
    report = "✅ <b>Все показания успешно сохранены и отправлены!</b>\n\n"
    
    names = {
        "electro": "⚡ Электроэнергия",
        "water_cold": "🚰 Холодная вода", 
        "expl": "🏢 Комм. услуги",
        "drainage": "💧 Водоотведение"
    }
    
    for reading_type, data in collected_data.items():
        label = names.get(reading_type, reading_type)
        report += f"{label}\n"
        
        if reading_type == 'water_cold':
            report += f"• Тариф: {data.get('tariff', 0)} руб./м³\n\n"
        elif reading_type in ['expl', 'drainage']:
            report += f"• Сумма: {data['amount']} руб.\n\n"
        else:
            report += f"• Объем: {data['volume']}\n"
            report += f"• Сумма: {data['amount']} руб.\n\n"
    
    if unexpected_expenses > 0:
        report += f"💰 <b>Непредвиденные расходы:</b> {unexpected_expenses} руб.\n"
    
    if documents:
        report += f"📎 <b>Приложено документов (непредвиденные расходы):</b> {len(documents)}\n"
    
    report += f"📅 Время отправки: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    
    # Финальный шаг - 100%
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ <b>Отправка завершена!</b>\n\n"
             f"{stages[9][1]} 100%\n\n"
             f"Данные отправлены {total_users} пользователям.",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(1)
    
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=report,
        reply_markup=admin_main_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    # Сбрасываем переменную расходов
    unexpected_expenses = 0.0
    
    await state.clear()
    await call.answer("✅ Рассылка завершена!")


# Функция для создания клавиатуры документов для непредвиденных расходов
def create_document_keyboard_unexpected(has_files: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для управления документами (непредвиденные расходы)"""
    buttons = []
    
    if has_files:
        buttons.append([InlineKeyboardButton(text="📎 Добавить еще", callback_data="add_more_docs_unexpected")])
        buttons.append([InlineKeyboardButton(text="✅ Отправить с документами", callback_data="send_with_docs_unexpected")])
        buttons.append([InlineKeyboardButton(text="📤 Отправить без документов", callback_data="skip_documents_unexpected")])
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_docs_unexpected")])
    else:
        buttons.append([InlineKeyboardButton(text="📎 Добавить файл", callback_data="add_document_unexpected")])
        buttons.append([InlineKeyboardButton(text="📤 Отправить без документов", callback_data="skip_documents_unexpected")])
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_docs_unexpected")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Обработчики для управления документами непредвиденных расходов
@admin_router.callback_query(F.data == "add_document_unexpected", AdminState.waiting_for_documents_unexpected)
async def add_unexpected_document_prompt(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Запрос на добавление документа для непредвиденных расходов"""
    await edit_admin_message(
        bot,
        call.message.message_id,
        "📎 <b>Отправьте файл</b>\n\n"
        "Поддерживаются любые форматы:\n"
        "📄 PDF, DOC, DOCX\n"
        "🖼️ JPG, PNG (отправьте изображение именно как фото, а не файлом)\n"
        "📊 XLS, XLSX\n\n"
        "После отправки файла появится меню.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_docs_menu_unexpected")]
        ]),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.confirming_documents_unexpected)
    await call.answer()

@admin_router.callback_query(F.data == "admin_method_manual", StateFilter(AdminState.choosing_method))
async def admin_method_manual(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    current_type = data.get("current_type")
    
    if current_type == "expl":
        await state.update_data(
            current_type=current_type,
            step="amount"
        )
        await state.set_state(AdminState.waiting_for_amount_expl)
        
        names = get_type_names()
        label = names.get(current_type, "")
        
        await edit_admin_message(
            bot,
            call.message.message_id,
            f"📊 Ввод показаний\n\n"
            f"Введите сумму с НДС для {label} (в рублях):\n"
            f"(например: 1250.75)",
            parse_mode="HTML"
        )
    elif current_type == "drainage":
        await state.update_data(
            current_type=current_type,
            step="amount"
        )
        await state.set_state(AdminState.waiting_for_amount_drainage)
        
        names = get_type_names()
        label = names.get(current_type, "")
        
        await edit_admin_message(
            bot,
            call.message.message_id,
            f"📊 Ввод показаний\n\n"
            f"Введите сумму {label} (в рублях):\n"
            f"(например: 1250.75)",
            parse_mode="HTML"
        )
    else:
        # Существующая логика для остальных типов
        await state.update_data(
            current_type=current_type,
            step="volume"
        )
        await state.set_state(AdminState.waiting_for_volume)
        
        units = get_type_units()
        unit = units.get(current_type, "")
        
        await edit_admin_message(
            bot,
            call.message.message_id,
            f"📊 Ввод показаний\n\n"
            f"Введите объем потребления {unit}:\n"
            f"(например: 125.5)",
            parse_mode="HTML"
        )
    await call.answer()

@admin_router.message(StateFilter(AdminState.waiting_for_amount_drainage))
async def process_drainage_amount_input(message: Message, state: FSMContext, bot: Bot):
    """Обработка введенного коэфицента водоотведения"""
    try:
        await message.delete()
    except:
        pass
    if message.chat.id != ADMIN_CHAT_ID:
        return
    str_len = message.text
    raw_text = message.text.replace(",", ".")
    
    try:
        amount = float(raw_text)
        if amount < 0:
            raise ValueError
    except ValueError:
        await send_to_admin_topic(
            bot,
            "⚠️ Ошибка ввода\n\n"
            "Пожалуйста, введите корректную сумму (положительное число).",
            reply_markup=cancel_keyboard()
        )
        return
    if len(str_len)<14:
        data = await state.get_data()
        current_type = data.get("current_type")
        
        # Сохраняем данные для эксплуатационных услуг
        global collected_data
        if current_type not in collected_data:
            collected_data[current_type] = {}
        
        # Только сумма для эксплуатационных услуг
        collected_data[current_type]["amount"] = amount
        
        names = get_type_labels()
        label = names.get(current_type, "")
        
        # Проверяем, все ли типы заполнены
        missing_types_for_users = []
        collected_types = list(collected_data.keys())
        
        # Проверяем, какие типы из ALL_TYPES отсутствуют
        missing_types = [t for t in ALL_TYPES if t not in collected_types]
        
        # Преобразуем в читаемые названия
        type_to_readable = {
            'electro': 'электричество',
            'water_cold': 'холодная вода',
            'expl': 'коммунальные услуги',
            'drainage': 'водоотведение'
        }
        
        for type_miss in missing_types:
            missing_types_for_users.append(type_to_readable.get(type_miss, type_miss))
        
        builder = InlineKeyboardBuilder()
        
        if missing_types:
            builder.button(text="📝 Добавить следующий показатель", callback_data="admin_add_next")
        else:
            builder.button(text="✏️ Редактировать показания", callback_data="admin_edit_menu")
            builder.button(text="💾 Сохранить все показания",style="success", callback_data="admin_save_all")
        
        builder.button(text="❌ Отмена", callback_data="admin_cancel")
        builder.adjust(1)
        
        await send_to_admin_topic(
            bot,
            f"✅ Данные сохранены:\n\n"
            f"{label}\n"
            f"• Ставка для водоотведения: {amount} руб.\n\n"
            f"Собрано показаний: {len(collected_types)} из 5\n\n"
            f"{'📋 Все показатели собраны!' if not missing_types else '📝 Осталось заполнить: ' + ', '.join(missing_types_for_users)}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
        await state.set_state(AdminState.collecting_data)
        
        try:
            await bot.delete_message(ADMIN_CHAT_ID, message.message_id)
        except:
            pass 
    else: 
        await send_to_admin_topic(
            bot,
            f"Пожалуйста введите корректное число"
        )
        try:
            await message.delete()
        except:
            pass

@admin_router.message(StateFilter(AdminState.waiting_for_amount_expl))
async def process_amount_expl_input(message: Message, state: FSMContext, bot: Bot):
    try:
        await message.delete()
    except:
        pass
    if message.chat.id != ADMIN_CHAT_ID:
        return
    str_len = message.text
    raw_text = message.text.replace(",", ".")
    
    try:
        amount = float(raw_text)
        if amount < 0:
            raise ValueError
    except ValueError:
        await send_to_admin_topic(
            bot,
            "⚠️ Ошибка ввода\n\n"
            "Пожалуйста, введите корректную сумму (положительное число).",
            reply_markup=cancel_keyboard()
        )
        return
    if len(str_len)<14:
        data = await state.get_data()
        current_type = data.get("current_type")  # Должно быть "expl"
        
        # Сохраняем данные для эксплуатационных услуг
        global collected_data
        if current_type not in collected_data:
            collected_data[current_type] = {}
        
        # Только сумма для эксплуатационных услуг
        collected_data[current_type]["amount"] = amount
        
        names = get_type_labels()
        label = names.get(current_type, "")
        
        # Проверяем, все ли типы заполнены
        missing_types_for_users = []
        collected_types = list(collected_data.keys())
        
        # Проверяем, какие типы из ALL_TYPES отсутствуют
        missing_types = [t for t in ALL_TYPES if t not in collected_types]
        
        # Преобразуем в читаемые названия
        type_to_readable = {
            'electro': 'электричество',
            'water_cold': 'холодная вода',
            'expl': 'коммунальные услуги',
            'drainage': 'водоотведение'
        }
        
        for type_miss in missing_types:
            missing_types_for_users.append(type_to_readable.get(type_miss, type_miss))
        
        builder = InlineKeyboardBuilder()
        
        if missing_types:
            builder.button(text="📝 Добавить следующий показатель", callback_data="admin_add_next")
        else:
            builder.button(text="✏️ Редактировать показания", callback_data="admin_edit_menu")
            builder.button(text="💾 Сохранить все показания",style="success", callback_data="admin_save_all")
        
        builder.button(text="❌ Отмена", callback_data="admin_cancel")
        builder.adjust(1)
        
        await send_to_admin_topic(
            bot,
            f"✅ Данные сохранены:\n\n"
            f"{label}\n"
            f"• Сумма с НДС: {amount} руб.\n\n"
            f"Собрано показаний: {len(collected_types)} из 5\n\n"
            f"{'📋 Все показатели собраны!' if not missing_types else '📝 Осталось заполнить: ' + ', '.join(missing_types_for_users)}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
        await state.set_state(AdminState.collecting_data)
        
        try:
            await bot.delete_message(ADMIN_CHAT_ID, message.message_id)
        except:
            pass
    else:
        await send_to_admin_topic(
            bot,
            f"Пожалуйста введите корректное число"
        )

@admin_router.message(StateFilter(AdminState.waiting_for_edit))
async def process_edit_input(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода нового значения при редактировании"""
    try:
        await message.delete()
    except:
        pass
    if message.chat.id != ADMIN_CHAT_ID:
        return
    
    raw_text = message.text.replace(",", ".")
    
    try:
        value = float(raw_text)
        if value < 0:
            raise ValueError
    except ValueError:
        await send_to_admin_topic(
            bot,
            "⚠️ Ошибка ввода\n\n"
            "Пожалуйста, введите корректное положительное число.",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    edit_type = data.get("edit_type")
    editing_field = data.get("editing_field")
    
    # Проверяем, есть ли такой тип
    if not edit_type:
        await send_to_admin_topic(
            bot,
            "❌ Ошибка: не указан тип показаний",
            reply_markup=cancel_keyboard()
        )
        return
    
    # ОБНОВЛЕНИЕ: Проверка для эксплуатационных услуг
    if edit_type == "expl" and editing_field == "volume":
        await send_to_admin_topic(
            bot,
            "❌ Ошибка: коммунальные услуги не имеют объема\n"
            "Пожалуйста, редактируйте только сумму.",
            reply_markup=cancel_keyboard()
        )
        return
    
    # Обновляем значение в collected_data
    global collected_data
    if edit_type not in collected_data:
        collected_data[edit_type] = {}
    
    collected_data[edit_type][editing_field] = value
    
    # Показываем обновленные данные
    field_names = {
        "volume": "объем",
        "amount": "сумма"
    }
    
    await state.set_state(AdminState.editing_data)
    
    builder = InlineKeyboardBuilder()
    
    # ОБНОВЛЕНИЕ: Для эксплуатационных услуг не показываем кнопку редактирования объема
    if edit_type != "expl":
        builder.button(text="📝 Редактировать объем", callback_data=f"admin_edit_volume_{edit_type}")
    
    builder.button(text="💰 Редактировать сумму", callback_data=f"admin_edit_amount_{edit_type}")
    builder.button(text="🔙 Назад к списку", callback_data="admin_edit_menu")
    builder.adjust(1)
    
    names = get_type_names()
    label = names.get(edit_type, "")
    
    # Безопасное получение данных для отображения
    type_data = collected_data.get(edit_type, {})
    
    message_text = f"✅ {field_names.get(editing_field, 'Значение')} обновлено!\n\n✏️ Показания {label}\n\nТекущие значения:\n"
    
    # ОБНОВЛЕНИЕ: Для эксплуатационных услуг не показываем объем
    if edit_type != "expl":
        message_text += f"• Объем: {type_data.get('volume', '—')}\n"
    
    message_text += f"• Сумма: {type_data.get('amount', '—')} руб.\n\nЧто еще хотите изменить?"
    
    await send_to_admin_topic(
        bot,
        message_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    
    # Удаляем сообщение с вводом
    try:
        await bot.delete_message(ADMIN_CHAT_ID, message.message_id)
    except:
        pass

@admin_router.message(StateFilter(AdminState.waiting_for_volume))
async def process_volume_input(message: Message, state: FSMContext, bot: Bot):
    """Обработка введенного объема"""
    if message.chat.id != ADMIN_CHAT_ID:
        return
    
    raw_text = message.text.replace(",", ".")
    
    try:
        str_len = message.text
        volume = float(raw_text)
        if volume < 0:
            raise ValueError
    except ValueError:
        # Если ошибка, удаляем ввод пользователя и шлем предупреждение
        try:
            await message.delete()
        except:
            pass
        await send_to_admin_topic(
            bot,
            "⚠️ Ошибка ввода\n\nВведите положительное число.",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        return
    if len(str_len) < 14:
        # 1. Достаем данные и ID старого сообщения бота
        data = await state.get_data()
        current_type = data.get("current_type")
        last_msg_id = data.get("last_msg_id")

        # 2. Удаляем ПРЕДЫДУЩЕЕ сообщение бота (где была кнопка)
        if last_msg_id:
            try:
                await bot.delete_message(chat_id=ADMIN_CHAT_ID, message_id=last_msg_id)
            except:
                pass

        # 3. Удаляем сообщение ПОЛЬЗОВАТЕЛЯ (введенное число)
        try:
            await message.delete()
        except:
            pass

        # Сохраняем данные
        global collected_data
        if current_type not in collected_data:
            collected_data[current_type] = {}
        collected_data[current_type]["volume"] = volume
        
        await state.update_data(step="amount")
        await state.set_state(AdminState.waiting_for_amount)
        
        names = {"electro": "электроэнергии", "water_cold": "холодной воды", "expl":"комм. услуги", "drainage": "водоотведение"}
        label = names.get(current_type, "")
        unit_of_measurement = ""
        if label == "электроэнергии":
            unit_of_measurement = "кВт·ч"
        elif label == "холодной воды":
            unit_of_measurement = "м³"
        
        # 4. Отправляем НОВОЕ сообщение и сохраняем его ID
        new_msg = await send_to_admin_topic(
            bot,
            f"✅ Объем сохранен: {volume} {unit_of_measurement}\n\n"
            f"Теперь введите сумму с НДС для {label} (в рублях):\n"
            f"(например: 1250.75)",
            parse_mode="HTML"
        )
        
        await state.update_data(last_msg_id=new_msg.message_id)
    else: 
        new_msg = await send_to_admin_topic(
        bot,
        f"Пожалуйста введите число короче",
        parse_mode="HTML"
        )
        await state.update_data(last_msg_id=new_msg.message_id)

@admin_router.message(StateFilter(AdminState.waiting_for_amount))
async def process_amount_input(message: Message, state: FSMContext, bot: Bot):
    """Обработка введенной суммы с НДС"""
    if message.chat.id != ADMIN_CHAT_ID:
        return
    
    raw_text = message.text.replace(",", ".")
    str_len = message.text
    try:
        amount = float(raw_text)
        if amount < 0:
            raise ValueError
    except ValueError:
        await send_to_admin_topic(
            bot,
            "⚠️ Ошибка ввода\n\n"
            "Пожалуйста, введите корректную сумму (положительное число).",
            reply_markup=cancel_keyboard()
        )
        return
    if len(str_len)<14:
        data = await state.get_data()
        current_type = data.get("current_type")
        
        # Сохраняем сумму для текущего типа
        global collected_data
        missing_types_for_users = []
        if current_type not in collected_data:
            collected_data[current_type] = {}
        
        collected_data[current_type]["amount"] = amount
        
        names = {
            "electro": "⚡ Электроэнергия",
            "water_cold": "🚰 Холодная вода", 
            "drainage": "💧 Водоотведение"
        }
        label = names.get(current_type, "")
        
        # Проверяем, все ли типы заполнены
        all_types = ["electro", "water_cold", "expl","drainage"]
        collected_types = list(collected_data.keys())
        
        missing_types = [t for t in all_types if t not in collected_types]
        for type_miss in missing_types:
            if type_miss == 'electro':
                missing_types_for_users.append('электричество')
            elif type_miss == 'water_cold':
                missing_types_for_users.append('холодная вода')
            elif type_miss == 'expl':
                missing_types_for_users.append('комм. услуги')
            elif type_miss == 'drainage':
                missing_types_for_users.append('водоотведение')
        
        builder = InlineKeyboardBuilder()
        
        if missing_types:
            # Есть еще не заполненные типы
            builder.button(text="📝 Добавить следующий показатель", callback_data="admin_add_next")
        else:
            # Все заполнено - можно редактировать или сохранять
            builder.button(text="✏️ Редактировать показания", callback_data="admin_edit_menu")
            builder.button(text="💾 Сохранить все показания",style="success", callback_data="admin_save_all")
        
        builder.button(text="❌ Отмена", callback_data="admin_cancel")
        builder.adjust(1)
        unit_of_measurement = ""
        print(label)
        if label == "⚡ Электроэнергия":
            unit_of_measurement = "кВт·ч"
        elif label == "🚰 Холодная вода":
            unit_of_measurement = "м³"
        await send_to_admin_topic(
            bot,
            f"✅ Данные сохранены:\n\n"
            f"{label}\n"
            f"• Объем: {collected_data[current_type]['volume']} {unit_of_measurement}\n"
            f"• Сумма с НДС: {amount} руб.\n\n"
            f"Собрано показаний: {len(collected_types)} из 5\n\n"
            f"{'📋 Все показатели собраны!' if not missing_types else '📝 Осталось заполнить: ' + ', '.join(missing_types_for_users)}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
        await state.set_state(AdminState.collecting_data)
        
        try:
            await bot.delete_message(ADMIN_CHAT_ID, message.message_id)
        except:
            pass
    else: 
        await send_to_admin_topic(
            bot,
            f"Пожалуйста введите корректное число"
        )

@admin_router.callback_query(F.data == "admin_edit_menu", 
                             StateFilter(AdminState.collecting_data, 
                                        AdminState.editing_data,
                                        AdminState.waiting_for_edit))
async def handle_edit_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    
    if current_state == AdminState.waiting_for_edit:
        data = await state.get_data()
        edit_type = data.get("edit_type")
        
        if edit_type:
            if edit_type not in collected_data:
                await call.answer(f"Показания для '{edit_type}' не найдены!", show_alert=True)
                # Возвращаем к основному меню редактирования
                await show_edit_menu_from_state(call, state, bot)
                return
            
            # Возвращаем к редактированию конкретного типа
            await state.set_state(AdminState.editing_data)
            
            names = get_type_names()
            label = names.get(edit_type, "")
            
            builder = InlineKeyboardBuilder()
            
            # Для эксплуатационных услуг нет кнопки редактирования объема
            if edit_type != "expl":
                builder.button(text="📝 Редактировать объем", callback_data=f"admin_edit_volume_{edit_type}")
            
            builder.button(text="💰 Редактировать сумму", callback_data=f"admin_edit_amount_{edit_type}")
            builder.button(text="🔙 Назад к списку", callback_data="admin_edit_menu")
            builder.adjust(1)
            
            # Безопасное получение данных
            type_data = collected_data.get(edit_type, {})
            
            message_text = f"✏️ Редактирование показаний {label}\n\nТекущие значения:\n"
            
            if edit_type == 'water_cold':
                message_text += f"• Тариф: {data.get('tariff', 0)} руб./м³\n\n"
            if edit_type != "expl" or edit_type!= "drainage":
                message_text += f"• Объем: {type_data.get('volume', '—')}\n"
            
            message_text += f"• Сумма: {type_data.get('amount', '—')} руб.\n\nЧто вы хотите изменить?"
            
            await edit_admin_message(
                bot,
                call.message.message_id,
                message_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        else:
            # Показываем общее меню редактирования
            await show_edit_menu_from_state(call, state, bot)
    
    elif current_state in [AdminState.collecting_data, AdminState.editing_data]:
        # Показываем общее меню редактирования
        await show_edit_menu_from_state(call, state, bot)
    
    await call.answer()

async def show_edit_menu_from_state(call: CallbackQuery, state: FSMContext, bot: Bot):
    global collected_data
    
    if not collected_data:
        await call.answer("Нет данных для редактирования!", show_alert=True)
        return
    
    await state.set_state(AdminState.collecting_data)
    
    # Формируем сообщение с текущими данными
    report = "📊 Текущие показания:\n\n"
    
    names = get_type_labels()
    
    for reading_type in ALL_TYPES:
        label = names.get(reading_type, reading_type)
        if reading_type in collected_data:
            data = collected_data[reading_type]
            report += f"✅ {label}\n"
            if reading_type == 'water_cold':
                report += f"• Тариф: {data.get('tariff', 0)} руб./м³\n\n"
            elif reading_type != "expl" or reading_type != "drainage":
                report += f"• Объем: {data.get('volume', '—')}\n"
                report += f"• Сумма: {data.get('amount', '—')} руб.\n\n"
            else:
                report += f"• Сумма: {data.get('amount', '—')} руб.\n\n"
        else:
            report += f"❌ {label} — не заполнено\n\n"
    
    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для редактирования каждого типа
    for reading_type in ALL_TYPES:
        if reading_type in collected_data:
            label = names.get(reading_type, "")
            builder.button(text=f"✏️ {label}", callback_data=f"admin_edit_{reading_type}")
    
    builder.button(text="💾 Сохранить все показания",style="success", callback_data="admin_save_all")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        report,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@admin_router.callback_query(F.data.startswith("admin_edit_"), StateFilter(AdminState.collecting_data))
async def start_edit_type(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Начать редактирование конкретного типа показаний"""
    edit_type = call.data.replace("admin_edit_", "")
    
    if edit_type not in ALL_TYPES:
        await call.answer("Неизвестный тип показаний", show_alert=True)
        return
    
    # ВАЖНО: Проверяем, есть ли данные для редактирования
    global collected_data
    if edit_type not in collected_data:
        await call.answer("Этот показатель еще не заполнен!", show_alert=True)
        
        # Показываем текущее состояние сбора данных
        await show_edit_menu_from_state(call, state, bot)
        return
    
    await state.update_data(edit_type=edit_type)
    await state.set_state(AdminState.editing_data)
    
    names = get_type_names()
    label = names.get(edit_type, "")
    
    builder = InlineKeyboardBuilder()
    
    # Разные кнопки в зависимости от типа
    if edit_type == "water_cold":
        # Для холодной воды - только тариф
        builder.button(text="💰 Редактировать тариф", callback_data=f"admin_edit_tariff_{edit_type}")
    elif edit_type == "expl" or edit_type == "drainage":
        # Для эксплуатационных услуг и водоотведения - только сумма
        builder.button(text="💰 Редактировать сумму", callback_data=f"admin_edit_amount_{edit_type}")
    else:
        # Для остальных (electro, water_hot) - объем и сумма
        builder.button(text="📝 Редактировать объем", callback_data=f"admin_edit_volume_{edit_type}")
        builder.button(text="💰 Редактировать сумму", callback_data=f"admin_edit_amount_{edit_type}")
    
    builder.button(text="🔙 Назад к списку", callback_data="admin_edit_menu")
    builder.adjust(1)
    
    # Безопасное получение данных
    type_data = collected_data.get(edit_type, {})
    
    message_text = f"✏️ Редактирование показаний {label}\n\nТекущие значения:\n"
    
    if edit_type == "water_cold":
        message_text += f"• Тариф: {type_data.get('tariff', '—')} руб./м³\n\n"
    elif edit_type == "expl" or edit_type == "drainage":
        message_text += f"• Сумма: {type_data.get('amount', '—')} руб.\n\n"
    else:
        message_text += f"• Объем: {type_data.get('volume', '—')}\n"
        message_text += f"• Сумма: {type_data.get('amount', '—')} руб.\n\n"
    
    message_text += "Что вы хотите изменить?"
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        message_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await call.answer()

@admin_router.callback_query(F.data.startswith("admin_edit_volume_"), StateFilter(AdminState.editing_data))
async def edit_volume_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Начать редактирование объема"""
    edit_type = call.data.replace("admin_edit_volume_", "")
    
    # Проверка существования данных
    if edit_type not in collected_data:
        await call.answer("Данные не найдены!", show_alert=True)
        await show_edit_menu_from_state(call, state, bot)
        return
    
    await state.update_data(
        edit_type=edit_type,
        editing_field="volume"
    )
    await state.set_state(AdminState.waiting_for_edit)
    
    units = get_type_units()
    unit = units.get(edit_type, "")
    
    # Безопасное получение текущего значения
    current_volume = collected_data.get(edit_type, {}).get('volume', '—')
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"✏️ Редактирование объема\n\n"
        f"Текущее значение: {current_volume}\n\n"
        f"Введите новое значение объема {unit}:\n"
        f"(например: 125.5)",
        reply_markup=cancel_keyboard(with_edit_option=True),
        parse_mode="HTML"
    )
    await call.answer()

@admin_router.callback_query(F.data.startswith("admin_edit_amount_"), StateFilter(AdminState.editing_data))
async def edit_amount_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Начать редактирование суммы"""
    edit_type = call.data.replace("admin_edit_amount_", "")
    
    # Проверка существования данных
    if edit_type not in collected_data:
        await call.answer("Данные не найдены!", show_alert=True)
        await show_edit_menu_from_state(call, state, bot)
        return
    
    await state.update_data(
        edit_type=edit_type,
        editing_field="amount"
    )
    
    # Выбираем правильное состояние в зависимости от типа
    if edit_type == "expl":
        await state.set_state(AdminState.waiting_for_amount_expl)
    elif edit_type == "drainage":
        await state.set_state(AdminState.waiting_for_amount_drainage)
    else:
        await state.set_state(AdminState.waiting_for_edit)
    
    # Безопасное получение текущего значения
    current_amount = collected_data.get(edit_type, {}).get('amount', '—')
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"✏️ Редактирование суммы\n\n"
        f"Текущее значение: {current_amount} руб.\n\n"
        f"Введите новую сумму с НДС (в рублях):\n"
        f"(например: 1250.75)",
        reply_markup=cancel_keyboard(with_edit_option=True),
        parse_mode="HTML"
    )
    await call.answer()

@admin_router.callback_query(F.data == "admin_add_next", StateFilter(AdminState.collecting_data))
async def add_next_reading(call: CallbackQuery, state: FSMContext, bot: Bot):
    # В колбэке мы просто редактируем текущее сообщение, 
    # поэтому старые кнопки исчезают сами (заменяются новыми)
    global collected_data
    collected_types = list(collected_data.keys())
    missing_types = [t for t in ALL_TYPES if t not in collected_types]
    
    if not missing_types:
        await call.answer("Все показатели уже заполнены!")
        return
    
    next_type = missing_types[0]
    
    if next_type == "expl":
        await state.update_data(current_type=next_type, step="amount")
        await state.set_state(AdminState.waiting_for_amount_expl)
        text = f"📊 Добавление следующего показателя\n\nВведите сумму для {get_type_names().get(next_type, '')}:"
    elif next_type == "drainage":
        await state.update_data(current_type=next_type, step="amount")
        await state.set_state(AdminState.waiting_for_amount_drainage)
        text = f"📊 Добавление следующего показателя\n\nВведите ставку для {get_type_names().get(next_type, '')}:"
    elif next_type == "water_cold":
        await state.update_data(current_type=next_type, step="tariff")
        await state.set_state(AdminState.waiting_for_tariff)
        text = f"📊 Добавление следующего показателя\n\nВведите тариф для {get_type_names().get(next_type, '')} (в рублях за м³):"
    else:
        await state.update_data(current_type=next_type, step="volume")
        await state.set_state(AdminState.waiting_for_volume)
        text = f"📊 Добавление следующего показателя\n\nВведите объем {get_type_units().get(next_type, '')}:"

    # Редактируем сообщение — это заменяет текст и кнопки
    await edit_admin_message(
        bot,
        call.message.message_id,
        text,
        parse_mode="HTML"
    )
    
    # Важно: запоминаем ID отредактированного сообщения
    await state.update_data(last_msg_id=call.message.message_id)
    await call.answer()

# @admin_router.callback_query(F.data == "admin_save_all", StateFilter(AdminState.collecting_data))
# async def save_all_readings(call: CallbackQuery, state: FSMContext, bot: Bot):
#     from handlers.excel_tg_test import admin_indicators, create_excel, get_volume_and_amount_month,count_tenant_excel,create_word
#     from main import bot
#     import asyncio
#     global collected_data
#     
#     await call.answer()
#     if not collected_data:
#         await call.answer("Нет данных для сохранения!", show_alert=True)
#         return
#     print(collected_data)
#     if 'heating' not in collected_data or not collected_data['heating']:
#         await call.message.answer(
#             "❌ <b>Отопление не заполнено!</b>\n\n"
#             "Сначала введите показания отопления."
#         )
#         # Возвращаем в меню
#         await state.set_state(AdminState.collecting_data)
        
#         # ПРОВЕРЯЕМ, нужно ли редактировать
#         current_text = call.message.text
#         new_text = "📊 <b>Сбор показателей</b>\n\nВыберите показатель для ввода:"
        
#         if current_text != new_text:  # Редактируем только если текст изменился
#             await edit_admin_message(
#                 bot,
#                 call.message.message_id,
#                 new_text,
#                 reply_markup=admin_main_keyboard()
#             )
#         return
#     else:

#         count_users = await count_tenant_excel()
#         # Показываем прогресс
#         stages = [
#             (10, "🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Подготовка данных..."),
#             (20, "🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Сохранение показателей..."),
#             (30, "🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Получение списка пользователей..."),
#             (40, "🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️", "Формирование отчетов..."),
#             (50, "🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️", "Создание Excel файлов..."),
#             (60, "🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️", "Отправка документов..."),
#             (70, "🟩🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️", "Отправка уведомлений..."),
#             (80, "🟩🟩🟩🟩🟩🟩🟩🟩⬛️⬛️", "Формирование отчета..."),
#             (90, "🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛️", "Завершение процесса..."),
#             (100, "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩", "✅ Готово!")
#         ]
        
#         # Шаг 1 - подготовка
#         await bot.edit_message_text(
#             chat_id=call.message.chat.id,
#             message_id=call.message.message_id,
#             text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                 f"{stages[0][1]} {stages[0][0]}%\n\n"
#                 f"{stages[0][2]}",
#             parse_mode=ParseMode.HTML
#         )
#         await asyncio.sleep(1)
        
#         print(collected_data)
        
#         # Шаг 2 - сохранение показателей
#         await bot.edit_message_text(
#             chat_id=call.message.chat.id,
#             message_id=call.message.message_id,
#             text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                 f"{stages[1][1]} {stages[1][0]}%\n\n"
#                 f"{stages[1][2]}",
#             parse_mode=ParseMode.HTML
#         )
#         await admin_indicators(collected_data)
#         await asyncio.sleep(0.5)
        
#         # Шаг 3 - получение списка пользователей
#         await bot.edit_message_text(
#             chat_id=call.message.chat.id,
#             message_id=call.message.message_id,
#             text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                 f"{stages[2][1]} {stages[2][0]}%\n\n"
#                 f"{stages[2][2]}",
#             parse_mode=ParseMode.HTML
#         )
        
#         all_users_record_list = await get_data('SELECT user_id FROM users')
#         list_users = []
#         for user in all_users_record_list:
#             list_users.append(user['user_id'])
        
#         await asyncio.sleep(0.5)
        
#         # Шаг 4-7 - обработка пользователей
#         total_users = len(list_users)
#         for idx, user in enumerate(list_users):
#             # Рассчитываем прогресс от 40% до 80%
#             progress = 40 + int((idx / total_users) * 40) if total_users > 0 else 60
            
#             # Выбираем индикатор
#             if progress < 50:
#                 indicator = "🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️"
#             elif progress < 60:
#                 indicator = "🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️"
#             elif progress < 70:
#                 indicator = "🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️"
#             elif progress < 80:
#                 indicator = "🟩🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️"
#             else:
#                 indicator = "🟩🟩🟩🟩🟩🟩🟩🟩⬛️⬛️"
            
#             await bot.edit_message_text(
#                 chat_id=call.message.chat.id,
#                 message_id=call.message.message_id,
#                 text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                     f"{indicator} {progress}%\n\n"
#                     f"Обработка пользователя {idx+1}/{total_users}...",
#                 parse_mode=ParseMode.HTML
#             )
#             start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%d.%m.%Y")
#             end = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%d.%m.%Y")
#             months_ru = {
#                 1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
#                 5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
#                 9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
#             }
#             prev = datetime.now().replace(day=1) - timedelta(days=1)
#             period_str = f"{months_ru[prev.month]} {prev.year}"
#             info_list = [end,start,end,period_str]
            
#             text_for_user = await get_volume_and_amount_month(user)
#             file = await create_word(collected_data,user,count_users,info_list)
#             document = FSInputFile(file)
#             await call.message.answer_document(document=document)
#             await bot.send_document(chat_id=int(user), document=document, caption='Ваш счёт на оплату за прошедший месяц')
#             await bot.send_message(chat_id=int(user), text=text_for_user)
            
#             await asyncio.sleep(0.3)
        
#         # Шаг 8 - формирование отчета
#         await bot.edit_message_text(
#             chat_id=call.message.chat.id,
#             message_id=call.message.message_id,
#             text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                 f"{stages[7][1]} {stages[7][0]}%\n\n"
#                 f"{stages[7][2]}",
#             parse_mode=ParseMode.HTML
#         )
        
#         # Временная заглушка
#         success = True
        
#         if success:
#             # Шаг 9 - завершение
#             await bot.edit_message_text(
#                 chat_id=call.message.chat.id,
#                 message_id=call.message.message_id,
#                 text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                     f"{stages[8][1]} {stages[8][0]}%\n\n"
#                     f"{stages[8][2]}",
#                 parse_mode=ParseMode.HTML
#             )
#             await asyncio.sleep(0.5)
            
#             report = "✅ Все показания успешно сохранены!\n\n"
            
#             names = {
#                 "electro": "⚡ Электроэнергия",
#                 "water_cold": "🚰 Холодная вода", 
#                 "expl": "🏢 Комм. услуги",
#                 "drainage": "💧 Водоотведение"
#             }
            
#             for reading_type, data in collected_data.items():
#                 label = names.get(reading_type, reading_type)
#                 report += f"{label}\n"
#                 if label == '🏢 Комм. услуги':
#                     report += f"• Сумма: {data['amount']} руб.\n\n"
#                 elif label == '💧 Водоотведение':
#                     report += f"• Ставка: {data['amount']} руб.\n\n"
#                 else:
#                     report += f"• Объем: {data['volume']}\n"
#                     report += f"• Сумма: {data['amount']} руб.\n\n"
            
#             report += f"📅 Время внесения: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
#             # Финальный шаг - 100%
#             await bot.edit_message_text(
#                 chat_id=call.message.chat.id,
#                 message_id=call.message.message_id,
#                 text=f"✅ <b>Сохранение завершено!</b>\n\n"
#                     f"{stages[9][1]} 100%\n\n"
#                     f"Данные успешно сохранены и отправлены {total_users} пользователям.",
#                 parse_mode=ParseMode.HTML
#             )
#             await asyncio.sleep(1)
            
#             await edit_admin_message(
#                 bot,
#                 call.message.message_id,
#                 report,
#                 reply_markup=admin_main_keyboard()
#             )
            
#             # Очищаем собранные данные
#             collected_data = {}
            
#         else:
#             await bot.edit_message_text(
#                 chat_id=call.message.chat.id,
#                 message_id=call.message.message_id,
#                 text=f"❌ <b>Ошибка при сохранении</b>\n\n"
#                     f"Не удалось записать данные в таблицу.",
#                 parse_mode=ParseMode.HTML
#             )
#             await asyncio.sleep(1)
            
#             await edit_admin_message(
#                 bot,
#                 call.message.message_id,
#                 "❌ Ошибка при сохранении\n\n"
#                 "Не удалось записать данные в таблицу.",
#                 reply_markup=admin_main_keyboard()
#             )
    
#     await state.set_state(AdminState.admin_menu)

@admin_router.callback_query(F.data == "admin_save_all", StateFilter(AdminState.collecting_data))
async def save_all_readings(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Сохранение всех показаний"""
    from handlers.excel_tg_test import admin_indicators, create_excel, get_volume_and_amount_month, count_tenant_excel, create_word
    from main import bot
    import asyncio
    global collected_data
    new_text=''
    await call.answer()
    if not collected_data:
        await call.answer("Нет данных для сохранения!", show_alert=True)
        return
    
    # Получаем список обработанных арендаторов по отоплению
    data = await state.get_data()
    processed_tenants = data.get('list_tenant', [])
    
    # Проверяем, все ли арендаторы по отоплению обработаны
    query = "SELECT b.id FROM bussines b ORDER BY b.name_company"
    users_records = await get_data(query) 
    all_tenant_ids = [user['id'] for user in users_records]
    
    # Проверка 1: Все ли арендаторы по отоплению заполнены
    # if sorted(all_tenant_ids) != sorted(processed_tenants):
    #     missing_tenants_count = len(all_tenant_ids) - len(processed_tenants)
    #     await call.message.answer(
    #         f"❌ <b>Отопление заполнено не полностью!</b>\n\n"
    #         f"Осталось арендаторов: {missing_tenants_count}\n"
    #         f"Сначала заполните отопление для всех арендаторов."
    #     )
    #     return
    
    # Проверка 2: Есть ли данные по отоплению в collected_data
    if 'heating' not in collected_data or not collected_data['heating']:
        new_text+="❌ Отопление не заполнено!\n\nСначала введите показания отопления.\n\n"
        # Возвращаем в меню
        await state.set_state(AdminState.collecting_data)
        
        # ПРОВЕРЯЕМ, нужно ли редактировать
        current_text = call.message.text
        new_text += "📊 <b>Сбор показателей</b>\n\nВыберите показатель для ввода:"
        
        if current_text != new_text:  # Редактируем только если текст изменился
            await edit_admin_message(
                bot,
                call.message.message_id,
                new_text,
                reply_markup=admin_main_keyboard()
            )
        return
    
    # Проверка 3: Все ли общие показатели заполнены
    required_common = ["electro", "water_cold", "expl", "drainage"]
    missing_common = []
    common_names = {
        'electro': '⚡ Электроэнергия',
        'water_cold': '🚰 Холодная вода',
        'expl': '🏢 Комм. услуги',
        'drainage': '💧 Водоотведение'
    }
    
    for req in required_common:
        if req not in collected_data or not collected_data[req]:
            missing_common.append(common_names[req])
    
    if missing_common:
        await call.message.answer(
            f"❌ <b>Не все общие показатели заполнены!</b>\n\n"
            f"Отсутствуют:\n" + "\n".join(missing_common)
        )
        return
    
    # ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - можно предлагать файлы и непредвиденные расходы
    await state.set_state(AdminState.collecting_data)
    
    # Показываем сводку и спрашиваем про дополнения
    report = "📊 <b>Все показатели собраны!</b>\n\n"
    
    # Отопление (суммарно)
    heating_data = collected_data.get('heating', {})
    report += f"🔥 Отопление (все арендаторы)\n"
    report += f"• Сумма: {heating_data.get('amount', 0)} руб.\n\n"
    
    # Общие показатели
    names = {
        "electro": "⚡ Электроэнергия",
        "water_cold": "🚰 Холодная вода", 
        "expl": "🏢 Комм. услуги",
        "drainage": "💧 Водоотведение"
    }
    
    for reading_type, data_item in collected_data.items():
        if reading_type == 'heating':
            continue
        label = names.get(reading_type, reading_type)
        report += f"{label}\n"
        
        if reading_type == "water_cold":
            report += f"• Тариф: {data_item.get('tariff', 0)} руб./м³\n\n"
        elif reading_type in ["expl", "drainage"]:
            report += f"• Сумма: {data_item.get('amount', 0)} руб.\n\n"
        else:
            report += f"• Объем: {data_item.get('volume', 0)}\n"
            report += f"• Сумма: {data_item.get('amount', 0)} руб.\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Добавить непредвиденные расходы", callback_data="admin_unexpected_expenses")
    builder.button(text="📎 Прикрепить документы", callback_data="admin_attach_documents")
    builder.button(text="✅ Отправить без дополнений", callback_data="admin_final_save")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        report + "\nЧто хотите добавить перед отправкой?",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await call.answer()

@admin_router.callback_query(F.data == "admin_attach_documents", StateFilter(AdminState.collecting_data))
async def attach_documents_prompt(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Запрос на прикрепление документов"""
    await state.set_state(AdminState.waiting_for_documents)
    
    # Инициализируем хранилище документов
    temp_documents['final'] = {
        'files': [],
        'message_id': call.message.message_id,
        'chat_id': call.message.chat.id
    }
    await state.update_data(doc_type='final')
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        "📎 <b>Прикрепите документы</b>\n\n"
        "Вы можете прикрепить подтверждающие документы (счета, акты, накладные).\n"
        "Поддерживаются любые форматы файлов.\n\n"
        "Можно прикрепить несколько файлов.",
        reply_markup=create_document_keyboard_final(has_files=False),
        parse_mode="HTML"
    )
    await call.answer()


def create_document_keyboard_final(has_files: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для управления документами при финальной отправке"""
    buttons = []
    
    if has_files:
        buttons.append([InlineKeyboardButton(text="📎 Добавить еще", callback_data="add_more_docs_final")])
        buttons.append([InlineKeyboardButton(text="✅ Готово, отправляем", callback_data="admin_final_save")])
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_docs_final")])
    else:
        buttons.append([InlineKeyboardButton(text="📎 Добавить файл", callback_data="add_document_final")])
        buttons.append([InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_documents_final")])
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_docs_final")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@admin_router.callback_query(F.data == "add_document_final", AdminState.waiting_for_documents)
async def add_final_document_prompt(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Запрос на добавление документа"""
    await state.set_state(AdminState.confirming_documents)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        "📎 <b>Отправьте файл</b>\n\n"
        "Поддерживаются любые форматы:\n"
        "📄 PDF, DOC, DOCX\n"
        "🖼️ JPG, PNG (отправьте изображение именно как фото, а не файлом)\n"
        "📊 XLS, XLSX\n\n"
        "После отправки файла появится меню.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_docs_menu_final")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()


def get_file_list_text(files):
    """Формирует текст списка файлов с правильными иконками"""
    lines = []
    for f in files:
        mime = (f.get('mime_type') or "").lower()
        name = f.get('file_name', 'Файл')
        if "image" in mime or name.endswith(('.jpg', '.jpeg', '.png')):
            icon = "🖼️"
        elif "video" in mime or name.endswith(('.mp4', '.mov', '.avi')):
            icon = "🎬"
        else:
            icon = "📄"
        lines.append(f"{icon} {name}")
    return "\n".join(lines)

@admin_router.message(AdminState.confirming_documents, F.document)
async def handle_document(message: Message, bot: Bot, state: FSMContext):
    """Обработка полученного документа"""
    if 'final' not in temp_documents:
        temp_documents['final'] = {'files': []}
    
    try:
        doc = message.document
        temp_documents['final']['files'].append({
            'file_id': doc.file_id,
            'file_name': doc.file_name,
            'file_size': doc.file_size,
            'mime_type': doc.mime_type
        })
        
        file_list = get_file_list_text(temp_documents['final']['files'])
        await message.answer(
            f"✅ <b>Документ добавлен!</b>\n\n<b>Загруженные файлы:</b>\n{file_list}\n\nМожете добавить еще или отправить.",
            reply_markup=create_document_keyboard_final(has_files=True),
            parse_mode="HTML"
        )
        await state.set_state(AdminState.waiting_for_documents)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@admin_router.message(AdminState.confirming_documents, F.photo)
async def process_final_photo(message: Message, state: FSMContext, bot: Bot):
    """Обработка полученного фото — сразу кешируем байты, пока URL не истёк"""
    if 'final' not in temp_documents:
        temp_documents['final'] = {'files': []}
    
    photo = message.photo[-1]
    
    # Скачиваем байты СРАЗУ, пока signed URL ещё жив
    cached_bytes = None
    if photo.file_id and photo.file_id.startswith("http"):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(photo.file_id) as resp:
                    if resp.status == 200:
                        cached_bytes = await resp.read()
        except Exception as e:
            logging.warning(f"Не удалось кешировать фото: {e}")
    
    temp_documents['final']['files'].append({
        'file_id': photo.file_id,
        'file_name': f"photo_{datetime.now().strftime('%H%M%S')}.jpg",
        'file_size': photo.file_size,
        'mime_type': 'image/jpeg',
        'cached_bytes': cached_bytes,  # Кешированные байты (или None)
    })
    
    file_list = get_file_list_text(temp_documents['final']['files'])
    await message.answer(
        f"✅ <b>Фото добавлено!</b>\n\n<b>Загруженные файлы:</b>\n{file_list}\n\nМожете добавить еще или отправить.",
        reply_markup=create_document_keyboard_final(has_files=True),
        parse_mode="HTML"
    )
    await state.set_state(AdminState.waiting_for_documents)

@admin_router.message(AdminState.confirming_documents, F.video)
async def process_final_video(message: Message, state: FSMContext, bot: Bot):
    """Обработка полученного видео — сразу кешируем байты"""
    if 'final' not in temp_documents:
        temp_documents['final'] = {'files': []}
    
    video = message.video

    # Скачиваем байты СРАЗУ, пока signed URL ещё жив
    cached_bytes = None
    if video.file_id and video.file_id.startswith("http"):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(video.file_id) as resp:
                    if resp.status == 200:
                        cached_bytes = await resp.read()
        except Exception as e:
            logging.warning(f"Не удалось кешировать видео: {e}")

    temp_documents['final']['files'].append({
        'file_id': video.file_id,
        'file_name': f"video_{datetime.now().strftime('%H%M%S')}.mp4",
        'file_size': getattr(video, 'file_size', 0),
        'mime_type': 'video/mp4',
        'cached_bytes': cached_bytes,
    })
    
    file_list = get_file_list_text(temp_documents['final']['files'])
    await message.answer(
        f"✅ <b>Видео добавлено!</b>\n\n<b>Загруженные файлы:</b>\n{file_list}\n\nМожете добавить еще или отправить.",
        reply_markup=create_document_keyboard_final(has_files=True),
        parse_mode="HTML"
    )
    await state.set_state(AdminState.waiting_for_documents)


@admin_router.callback_query(F.data == "add_more_docs_final", AdminState.waiting_for_documents)
async def add_more_final_docs(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Добавление еще документов"""
    await add_final_document_prompt(call, state, bot)


@admin_router.callback_query(F.data == "back_to_docs_menu_final", AdminState.confirming_documents)
async def back_to_final_docs_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Возврат в меню документов"""
    await state.set_state(AdminState.waiting_for_documents)
    
    if 'final' in temp_documents and temp_documents['final']['files']:
        file_list = "\n".join([f"📄 {f['file_name']}" for f in temp_documents['final']['files']])
        text = f"📎 <b>Прикрепленные документы</b>\n\n<b>Загруженные файлы:</b>\n{file_list}"
    else:
        text = "📎 <b>Прикрепите документы</b>\n\nПока файлов нет."
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        text,
        reply_markup=create_document_keyboard_final(has_files=bool(temp_documents.get('final', {}).get('files'))),
        parse_mode="HTML"
    )
    await call.answer()


@admin_router.callback_query(F.data == "skip_documents_final")
async def skip_final_documents(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Пропустить документы"""
    await proceed_with_final_save(call, state, bot, documents=[])


@admin_router.callback_query(F.data == "cancel_docs_final")
async def cancel_final_documents(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Отмена добавления документов"""
    if 'final' in temp_documents:
        del temp_documents['final']
    
    await state.set_state(AdminState.collecting_data)
    
    # Возвращаемся в меню сбора данных
    global collected_data
    collected_types = list(collected_data.keys())
    
    # Проверяем, все ли типы заполнены
    all_types = ["electro", "water_cold", "water_hot", "expl", "drainage", "heating"]
    missing_types = [t for t in all_types if t not in collected_types]
    
    names = get_type_labels()
    
    if missing_types:
        # Есть незаполненные типы
        missing_names = [names.get(t, t) for t in missing_types]
        await edit_admin_message(
            bot,
            call.message.message_id,
            f"📊 <b>Сбор показателей</b>\n\n"
            f"Заполнено: {len(collected_types)} из {len(all_types)}\n"
            f"Осталось: {', '.join(missing_names)}",
            reply_markup=admin_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        # Всё заполнено
        report = "📊 <b>Все показатели собраны!</b>\n\n"
        
        # Отопление
        if 'heating' in collected_data:
            heating_data = collected_data.get('heating', {})
            report += f"🔥 Отопление\n"
            report += f"• Сумма: {heating_data.get('amount', 0)} руб.\n\n"
        
        # Общие показатели
        for reading_type, data_item in collected_data.items():
            if reading_type == 'heating':
                continue
            label = names.get(reading_type, reading_type)
            report += f"{label}\n"
            
            if reading_type == "water_cold":
                report += f"• Тариф: {data_item.get('tariff', 0)} руб./м³\n\n"
            elif reading_type in ["expl", "drainage"]:
                report += f"• Сумма: {data_item.get('amount', 0)} руб.\n\n"
            else:
                report += f"• Объем: {data_item.get('volume', 0)}\n"
                report += f"• Сумма: {data_item.get('amount', 0)} руб.\n\n"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="💰 Непредвиденные расходы", callback_data="admin_unexpected_expenses")
        builder.button(text="📎 Прикрепить документы", callback_data="admin_attach_documents")
        builder.button(text="✅ Отправить", callback_data="admin_final_save")
        builder.button(text="❌ Отмена", callback_data="admin_cancel")
        builder.adjust(1)
        
        await edit_admin_message(
            bot,
            call.message.message_id,
            report,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    
    await call.answer()


@admin_router.callback_query(F.data == "admin_final_save")
async def admin_final_save(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Финальное сохранение и отправка"""
    documents = temp_documents.get('final', {}).get('files', [])
    await proceed_with_final_save(call, state, bot, documents)


async def proceed_with_final_save(call: CallbackQuery, state: FSMContext, bot: Bot, documents: list):
    """Финальная отправка с непредвиденными расходами и документами"""
    from handlers.excel_tg_test import admin_indicators, get_volume_and_amount_month, count_tenant_excel, create_word
    import os
    
    data = await state.get_data()
    unexpected_expenses = data.get("unexpected_expenses", 0.0)
    print(f'ПРОВЕРКА НЕПРЕДВИДЕННЫХ РАСХОДОВ - {unexpected_expenses}')
    global collected_data
    
    # Анимация загрузки
    stages = [
        (10, "🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Подготовка данных..."),
        (20, "🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Сохранение показателей..."),
        (30, "🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Получение списка пользователей..."),
        (40, "🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️", "Формирование отчетов..."),
        (50, "🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️", "Создание Excel файлов..."),
        (60, "🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️", "Отправка документов..."),
        (70, "🟩🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️", "Отправка уведомлений..."),
        (80, "🟩🟩🟩🟩🟩🟩🟩🟩⬛️⬛️", "Формирование отчета..."),
        (90, "🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛️", "Завершение процесса..."),
        (100, "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩", "✅ Готово!")
    ]
    
    # Шаг 1 - подготовка
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔄 <b>Отправка данных...</b>\n\n"
             f"{stages[0][1]} {stages[0][0]}%\n\n"
             f"{stages[0][2]}",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.5)
    
    # Подготовка периода
    start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%d.%m.%Y")
    end = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%d.%m.%Y")
    prev = datetime.now().replace(day=1) - timedelta(days=1)
    
    months_ru = {
                1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
                5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
                9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
            }
    prev = datetime.now().replace(day=1) - timedelta(days=1)
    period_str = f"{months_ru[prev.month]} {prev.year}"
    info_list = [end,start,end,period_str]
    
    # Шаг 2 - сохранение показателей
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔄 <b>Отправка данных...</b>\n\n"
             f"{stages[1][1]} {stages[1][0]}%\n\n"
             f"{stages[1][2]}",
        parse_mode=ParseMode.HTML
    )
    await admin_indicators(collected_data)
    await asyncio.sleep(0.3)
    
    # Шаг 3 - получение списка пользователей
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔄 <b>Отправка данных...</b>\n\n"
             f"{stages[2][1]} {stages[2][0]}%\n\n"
             f"{stages[2][2]}",
        parse_mode=ParseMode.HTML
    )
    
    all_users = await get_data('SELECT User_Id as user_id FROM users')
    list_users = [user['user_id'] for user in all_users]
    count_users = await count_tenant_excel()
    await asyncio.sleep(0.3)
    
    # Шаги 4-7 - отправка пользователям
    total_users = len(list_users)
    for idx, user in enumerate(list_users):
        progress = 40 + int((idx / total_users) * 40) if total_users > 0 else 60
        
        if progress < 50:
            indicator = "🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️"
        elif progress < 60:
            indicator = "🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️"
        elif progress < 70:
            indicator = "🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️"
        elif progress < 80:
            indicator = "🟩🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️"
        else:
            indicator = "🟩🟩🟩🟩🟩🟩🟩🟩⬛️⬛️"
        
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🔄 <b>Отправка данных...</b>\n\n"
                 f"{indicator} {progress}%\n\n"
                 f"Отправка пользователю {idx+1}/{total_users}...",
            parse_mode=ParseMode.HTML
        )
        
        # Создаем и отправляем счет
        # text_for_user = await get_volume_and_amount_month(user)
        print(f"{collected_data}")
        print(f"Пользователь {user}")
        print(f"{count_users}")
        print(f"{info_list}")
        print(f"{unexpected_expenses}")
        from handlers.run import get_info_business
        from handlers.meter_readings import get_sheet_name
        file = await create_word(user, count_users, collected_data, info_list, unexpected_expenses, get_info_business, get_sheet_name)
        
        if file is None:
            await bot.send_message(
                chat_id=call.message.chat.id,
                text=f"⚠️ <b>Ошибка генерации документа!</b>\n"
                     f"Не удалось создать файл для пользователя <code>{user}</code> (скорее всего, в Excel нет показаний дат за прошлый/текущий месяц). Выставляем счёт следующему арендатору...",
                parse_mode="HTML"
            )
            continue
            
        document = FSInputFile(file)
        
        caption = '🧾 Ваш счёт за прошедший месяц'
        if unexpected_expenses > 0:
            caption += f'\n\n💰 Непредвиденные расходы: {unexpected_expenses} руб.'
        
        sent_message = await bot.send_document(
            chat_id=int(user),
            document=document,
            caption=caption
        )
        today_date = date.today()
        file_id = sent_message.document.file_id
        records = await get_data('SELECT id_business FROM users WHERE User_Id = $1',str(user))
        if not records or not records[0]['id_business']:
            logging.warning(f"Пользователь {user} не найден в таблице Users или не привязан к бизнесу. Пропускаем запись документа.")
            id_business = None
        else:
            id_business = records[0]['id_business']
            await new_data_insert('INSERT INTO business_documents(id_business,file_id, date_added) VALUES ($1, $2, $3)',id_business, file_id, today_date)
        
        # Дублируем файл в админский чат
        await bot.send_document(
            chat_id=call.message.chat.id,
            document=FSInputFile(file),
            caption=f"📁 Копия счёта, отправленного арендатору: <code>{user}</code>",
            parse_mode="HTML"
        )
        
        os.unlink(file)
        
        # Отправляем приложенные документы
        for doc in documents:
            mime = (doc.get('mime_type') or "").lower()
            file_id = doc.get('file_id')
            file_name = doc.get('file_name', 'Счет')
            cached_bytes = doc.get('cached_bytes')
            
            if "image" in mime or file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                # Фото — используем кешированные байты если есть
                if cached_bytes:
                    from aiogram.types.input_file import BufferedInputFile
                    photo_input = BufferedInputFile(cached_bytes, filename=file_name)
                    await bot.send_photo(
                        chat_id=int(user),
                        photo=photo_input,
                        caption=f"📸 Подтверждающее фото"
                    )
                else:
                    await bot.send_photo(
                        chat_id=int(user),
                        photo=file_id,
                        caption=f"📸 Подтверждающее фото"
                    )
            elif "video" in mime or file_name.lower().endswith(('.mp4', '.mov', '.avi')):
                if cached_bytes:
                    from aiogram.types.input_file import BufferedInputFile
                    video_input = BufferedInputFile(cached_bytes, filename=file_name)
                    await bot.send_video(
                        chat_id=int(user),
                        video=video_input,
                        caption=f"🎬 Подтверждающее видео"
                    )
                else:
                    await bot.send_video(
                        chat_id=int(user),
                        video=file_id,
                        caption=f"🎬 Подтверждающее видео"
                    )
            else:
                # Это документ - отправляем как документ (токен для файлов работает)
                await bot.send_document(
                    chat_id=int(user),
                    document=file_id,
                    caption=f"📎 Подтверждающий документ: {file_name}"
                )
        
        # await bot.send_message(chat_id=int(user), text=text_for_user)
        await asyncio.sleep(0.2)
    
    # Шаг 8 - формирование отчета
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔄 <b>Отправка данных...</b>\n\n"
             f"{stages[7][1]} {stages[7][0]}%\n\n"
             f"{stages[7][2]}",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.3)
    
    # Шаг 9 - завершение
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔄 <b>Отправка данных...</b>\n\n"
             f"{stages[8][1]} {stages[8][0]}%\n\n"
             f"{stages[8][2]}",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.3)
    
    # Очищаем временные данные
    if 'final' in temp_documents:
        del temp_documents['final']
    
    # Финальный отчет
    report = "✅ <b>Все показания успешно сохранены и отправлены!</b>\n\n"
    
    names = {
        "electro": "⚡ Электроэнергия",
        "water_cold": "🚰 Холодная вода", 
        "expl": "🏢 Комм. услуги",
        "drainage": "💧 Водоотведение"
    }
    
    for reading_type, data in collected_data.items():
        label = names.get(reading_type, reading_type)
        report += f"{label}\n"
        
        if reading_type == "water_cold":
            report += f"• Тариф: {data.get('tariff', 0)} руб./м³\n\n"
        elif reading_type in ["expl", "drainage"]:
            report += f"• Сумма: {data.get('amount', 0)} руб.\n\n"
        else:
            report += f"• Объем: {data.get('volume', 0)}\n"
            report += f"• Сумма: {data.get('amount', 0)} руб.\n\n"
    
    if unexpected_expenses > 0:
        report += f"💰 <b>Непредвиденные расходы:</b> {unexpected_expenses} руб.\n"
    
    if documents:
        report += f"📎 <b>Приложено документов:</b> {len(documents)}\n"
    
    report += f"📅 Время отправки: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    
    # Финальный шаг - 100%
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ <b>Отправка завершена!</b>\n\n"
             f"{stages[9][1]} 100%\n\n"
             f"Данные отправлены {total_users} пользователям.",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(1)
    
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=report,
        reply_markup=admin_main_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    # Очищаем данные
    collected_data = {}
    await state.clear()
    await call.answer("✅ Рассылка завершена!")


@admin_router.callback_query(F.data == "admin_method_pdf", StateFilter(AdminState.choosing_method))
async def admin_method_pdf(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Выбран способ через PDF файл"""
    await state.set_state(AdminState.waiting_for_file)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        "Данная функция на стадии разработки",
        reply_markup=cancel_keyboard()
    )
    await call.answer()

@admin_router.callback_query(F.data == "admin_refresh")
async def admin_refresh(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Обновить панель"""
    # Запрос: получить общее количество пользователей
    query = "SELECT COUNT(*) as count FROM users"
    result = await get_data(query)
    total_users = result[0]['count'] if result else 0
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"🔐 Административная панель (обновлено)\n\n"
        f"👥 Пользователей: {total_users}\n\n"
        "Выберите действие:",
        reply_markup=admin_main_keyboard()
    )
    await call.answer("✅ Обновлено")

@admin_router.callback_query(F.data == "admin_to_main")
async def back_to_main(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Вернуться в главное меню"""
    # Запрос: получить общее количество пользователей
    query = "SELECT COUNT(*) as count FROM users"
    result = await get_data(query)
    total_users = result[0]['count'] if result else 0
    
    await state.set_state(AdminState.admin_menu)
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"🔐 Административная панель\n\n"
        f"👥 Пользователей: {total_users}\n\n"
        "Выберите действие:",
        reply_markup=admin_main_keyboard()
    )
    await call.answer()

@admin_router.callback_query(F.data == "admin_cancel")
async def admin_cancel(call: CallbackQuery, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    
    if current_state in [AdminState.collecting_data, AdminState.editing_data, AdminState.waiting_for_edit]:
        # Если мы в процессе сбора/редактирования данных
        global collected_data
        
        if collected_data:
            # Показываем меню редактирования с текущими данными
            await state.set_state(AdminState.collecting_data)
            
            # Формируем сообщение с текущими данными
            report = "📊 Текущие показания:\n\n"
            
            names = {
                "electro": "⚡ Электроэнергия",
                "water_cold": "🚰 Холодная вода", 
                "expl": "🏢 Комм. услуги",
                "drainage": "💧 Водоотведение"
            }
            
            all_types = ["electro", "water_cold", "expl", "drainage"]
            
            for reading_type in all_types:
                label = names.get(reading_type, reading_type)
                if reading_type in collected_data:
                    data = collected_data[reading_type]
                    report += f"✅ {label}\n"
                    report += f"• Объем: {data.get('volume', '—')}\n"
                    report += f"• Сумма: {data.get('amount', '—')} руб.\n\n"
                else:
                    report += f"❌ {label} — не заполнено\n\n"
            
            builder = InlineKeyboardBuilder()
            
            # Проверяем, все ли типы заполнены
            collected_types = list(collected_data.keys())
            missing_types = [t for t in all_types if t not in collected_types]
            
            if missing_types:
                # Есть не заполненные типы
                builder.button(text="📝 Добавить следующий показатель", callback_data="admin_add_next")
                builder.button(text="✏️ Редактировать заполненные", callback_data="admin_edit_menu")
            else:
                # Все заполнено
                builder.button(text="✏️ Редактировать показания", callback_data="admin_edit_menu")
                builder.button(text="💾 Сохранить все показания", callback_data="admin_save_all")
            
            builder.button(text="🏠 В главное меню", callback_data="admin_to_main")
            builder.adjust(1)
            
            await edit_admin_message(
                bot,
                call.message.message_id,
                report,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        else:
            # Нет данных - возвращаем в главное меню
            await return_to_main_menu(call, state, bot)
    else:
        # Для всех других состояний - возврат в главное меню
        await return_to_main_menu(call, state, bot)
    
    await call.answer()

async def return_to_main_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Возврат в главное меню администратора"""
    # Запрос: получить общее количество пользователей
    query = "SELECT COUNT(*) as count FROM users"
    result = await get_data(query)
    total_users = result[0]['count'] if result else 0
    
    await state.set_state(AdminState.admin_menu)
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"🔐 Административная панель\n\n"
        f"👥 Пользователей: {total_users}\n\n"
        "Выберите действие:",
        reply_markup=admin_main_keyboard()
    )
    await call.answer()

# ===== РАССЫЛКА =====

@admin_router.callback_query(F.data == "admin_broadcast_all")
async def broadcast_all(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Рассылка всем пользователям"""
    # Запрос: получить количество активных пользователей
    query = "SELECT COUNT(*) as count FROM users"
    result = await get_data(query)
    total_users = result[0]['count'] if result else 0
    
    await state.update_data(audience="all", selected_users=[])
    await state.set_state(AdminState.waiting_for_message)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"📢 Рассылка всем пользователям\n\n"
        f"📊 Будет отправлено: {total_users} пользователям\n\n"
        "Отправьте сообщение в этот чат:\n"
        "(текст, фото, видео или документ)",
        reply_markup=cancel_keyboard()
    )
    await call.answer()

@admin_router.callback_query(F.data == "admin_broadcast_select")
async def broadcast_select(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Выборочная рассылка"""
    # Запрос: получить всех активных пользователей с названиями компаний
    query = """
    SELECT u.User_Id as user_id, b.name_company 
    FROM users u 
    JOIN bussines b ON b.id = u.id_business
    ORDER BY b.name_company
    """
    
    results = await get_data(query)
    
    if not results:
        await call.answer("❌ Нет пользователей для рассылки", show_alert=True)
        return
    
    # Преобразуем результаты в нужный формат
    users_data = []
    for result in results:
        users_data.append({
            'user_id': result['user_id'],
            'name_company': result['name_company'],
            'display_name': result['name_company']  # Используем название компании для отображения
        })
    
    await state.update_data(
        audience="select",
        selected_users=[],  # Здесь будем хранить выбранные user_id
        all_users=users_data,  # Полный список данных пользователей
        page=0
    )
    await state.set_state(AdminState.selecting_users)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"👥 Выберите получателей\n\n"
        f"Всего пользователей: {len(users_data)}\n"
        f"Выбрано: 0\n\n"
        "Используйте кнопки для выбора:",
        reply_markup=users_selection_keyboard(users_data, [], 0)
    )
    await call.answer()

@admin_router.callback_query(F.data.startswith("admin_page_"), StateFilter(AdminState.selecting_users))
async def change_page(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Смена страницы при выборе пользователей"""
    page = int(call.data.split("_")[2])
    data = await state.get_data()
    users = data.get("all_users", [])
    selected = data.get("selected_users", [])
    
    await state.update_data(page=page)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"👥 Выберите получателей\n\n"
        f"Всего пользователей: {len(users)}\n"
        f"Выбрано: {len(selected)}\n\n",
        reply_markup=users_selection_keyboard(users, selected, page)
    )
    await call.answer()

@admin_router.callback_query(F.data.startswith("admin_toggle_"), StateFilter(AdminState.selecting_users))
async def toggle_user(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Выбор/отмена пользователя"""
    user_id = str(call.data.split("_")[2])  # Получаем user_id как строку
    
    data = await state.get_data()
    selected = data.get("selected_users", [])  # Здесь хранятся user_id
    users_data = data.get("all_users", [])  # Полные данные пользователей
    page = data.get("page", 0)
    
    # Добавляем или удаляем user_id (используем строки для надежности)
    if str(user_id) in [str(s) for s in selected]:
        selected = [s for s in selected if str(s) != str(user_id)]
    else:
        selected.append(str(user_id))
    
    await state.update_data(selected_users=selected)
    
    # Получаем имена выбранных компаний для информации
    selected_companies = []
    for user in users_data:
        if user['user_id'] in selected:
            selected_companies.append(user.get('name_company', f"ID: {user['user_id']}"))
    
    display_text = "\n".join([f"• {name}" for name in selected_companies[:3]])
    if len(selected_companies) > 3:
        display_text += f"\n• ... и еще {len(selected_companies) - 3}"
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"👥 Выберите получателей\n\n"
        f"Всего пользователей: {len(users_data)}\n"
        f"✅ Выбрано: {len(selected)}\n\n"
        f"{'Выбранные компании:' if selected else ''}\n"
        f"{display_text if selected else ''}\n\n",
        reply_markup=users_selection_keyboard(users_data, selected, page)
    )
    await call.answer(f"{'Выбрано' if user_id in selected else 'Снято'}: {user_id}")

@admin_router.callback_query(F.data == "admin_select_all", StateFilter(AdminState.selecting_users))
async def select_all(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Выбрать всех пользователей"""
    data = await state.get_data()
    users_data = data.get("all_users", [])
    page = data.get("page", 0)
    
    # Собираем все user_id
    selected = [user['user_id'] for user in users_data]
    
    await state.update_data(selected_users=selected)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"👥 Выбраны все пользователи\n\n"
        f"Всего компаний: {len(users_data)}\n"
        f"✅ Выбрано: {len(selected)}\n\n",
        reply_markup=users_selection_keyboard(users_data, selected, page)
    )
    await call.answer("✅ Все компании выбраны")

@admin_router.callback_query(F.data == "admin_deselect_all", StateFilter(AdminState.selecting_users))
async def deselect_all(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Снять всех пользователей"""
    data = await state.get_data()
    users_data = data.get("all_users", [])
    page = data.get("page", 0)
    
    await state.update_data(selected_users=[])
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"👥 Выбор сброшен\n\n"
        f"Всего пользователей: {len(users_data)}\n"
        f"Выбрано: 0\n\n",
        reply_markup=users_selection_keyboard(users_data, [], page)
    )
    await call.answer("❌ Выбор сброшен")

@admin_router.callback_query(F.data == "admin_continue_selection", StateFilter(AdminState.selecting_users))
async def continue_selection(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Продолжить после выбора пользователей"""
    data = await state.get_data()
    selected = data.get("selected_users", [])
    
    if not selected:
        await call.answer("❌ Выберите хотя бы одного пользователя", show_alert=True)
        return
    
    await state.set_state(AdminState.waiting_for_message)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"👥 Выбрано пользователей: {len(selected)}\n\n"
        "Отправьте сообщение в этот чат:\n"
        "(текст, фото, видео или документ)",
        reply_markup=cancel_keyboard()
    )
    await call.answer()

@admin_router.message(StateFilter(AdminState.waiting_for_message))
async def get_message_for_broadcast(message: Message, state: FSMContext, bot: Bot):
    """Получить сообщение для рассылки"""
    if message.chat.id != ADMIN_CHAT_ID:
        return

    data = await state.get_data()
    audience = data.get("audience", "all")
    selected_users = data.get("selected_users", [])
    admin_message_id = data.get("admin_message_id")
    
    # Сохраняем данные сообщения
    message_data = {
        "message_type": "text",
        "message_content": message.text,
        "caption": None
    }
    
    if message.photo:
        message_data.update({
            "message_type": "photo",
            "message_content": message.photo[-1].file_id,
            "caption": message.caption
        })
    elif message.video:
        message_data.update({
            "message_type": "video",
            "message_content": message.video.file_id,
            "caption": message.caption
        })
    elif message.document:
        message_data.update({
            "message_type": "document",
            "message_content": message.document.file_id,
            "filename": message.document.file_name,
            "caption": message.caption
        })
    elif not message.text:
        await send_to_admin_topic(bot, "❌ Поддерживаются только текст, фото, видео и документы")
        return
    
    await state.update_data(message_data)
    
    # Формируем предпросмотр
    if message.text:
        preview = f"📝 Текст:\n`{message.text[:150]}{'...' if len(message.text) > 150 else ''}`"
    else:
        media_type = {
            "photo": "📷 Фото",
            "video": "🎬 Видео",
            "document": "📎 Документ"
        }.get(message_data["message_type"], "Сообщение")
        preview = f"{media_type}"
        if message.caption:
            preview += f"\n\n📝 Подпись:\n`{message.caption[:100]}{'...' if len(message.caption) > 100 else ''}`"
    
    if audience == "all":
        # Запрос: получить количество пользователей для рассылки
        query = "SELECT COUNT(*) as count FROM users"
        result = await get_data(query)
        users_count = result[0]['count'] if result else 0
        preview += f"\n\n👥 Получатели: Все ({users_count} чел.)"
    else:
        preview += f"\n\n👥 Получатели: Выбранные ({len(selected_users)} чел.)"
    
    # Отправляем НОВОЕ сообщение с предпросмотром (чтобы было внизу чата)
    admin_message = await send_to_admin_topic(
        bot,
        f"📋 Предпросмотр рассылки\n\n{preview}\n\n"
        "Подтвердите отправку:",
        reply_markup=confirm_keyboard()
    )
    if admin_message:
        await state.update_data(admin_message_id=admin_message.message_id)

    await state.set_state(AdminState.confirming_send)

    # Удаляем исходное сообщение пользователя (для чистоты)
    try:
        await bot.delete_message(ADMIN_CHAT_ID, message.message_id)
    except:
        pass

@admin_router.callback_query(F.data == "admin_edit_message", StateFilter(AdminState.confirming_send))
async def edit_broadcast_message(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.set_state(AdminState.waiting_for_message)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        "✏️ Редактирование сообщения\n\n"
        "Отправьте новое сообщение в этот чат:\n"
        "(текст, фото, видео или документ)",
        reply_markup=cancel_keyboard()
    )
    await call.answer()

@admin_router.callback_query(F.data == "admin_confirm_send", StateFilter(AdminState.confirming_send))
async def confirm_broadcast(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтвердить и отправить рассылку"""
    data = await state.get_data()
    message_type = data.get("message_type")
    message_content = data.get("message_content")
    caption = data.get("caption", "")
    audience = data.get("audience", "all")
    selected_users = data.get("selected_users", [])
    
    # Определяем получателей
    if audience == "all":
        # Запрос: получить ID всех активных пользователей кроме отправителя
        query = "SELECT User_Id FROM Users WHERE User_Id != $1"
        result = await get_data(query, str(call.message.chat.id))
        targets = [row['user_id'] for row in result] if result else []
    else:
        targets = selected_users
    
    if not targets:
        await edit_admin_message(bot, call.message.message_id, "❌ Нет получателей для рассылки")
        await state.set_state(AdminState.admin_menu)
        return
    
    # У MAX API не всегда получается скачивать файлы по внешним ссылкам.
    # Если это медиафайл и он сохранен в виде URL, скачаем его заранее в память.
    media_bytes = None
    if message_type in ("photo", "video", "document") and isinstance(message_content, str) and message_content.startswith("http"):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(message_content) as resp:
                    if resp.status == 200:
                        media_bytes = await resp.read()
        except Exception as e:
            logging.error(f"Failed to pre-download media for broadcast: {e}")

    # Начинаем рассылку
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"🚀 Начинаю рассылку...\n\n"
        f"📊 Прогресс: 0/{len(targets)}\n"
        f"✅ Успешно: 0\n"
        f"❌ Ошибок: 0"
    )
    
    success = 0
    failed = 0
    
    # Подготавливаем медиафайл один раз перед циклом
    current_media = message_content
    if media_bytes:
        import os as _os
        from aiogram.types.input_file import BufferedInputFile
        orig_fname = data.get("filename")
        if not orig_fname:
            ext = "jpg" if message_type == "photo" else "mp4" if message_type == "video" else "bin"
            orig_fname = f"broadcast_media.{ext}"
        # Передаём полное имя с расширением — maxapi теперь умеет сохранять его без дублирования
        current_media = BufferedInputFile(media_bytes, filename=orig_fname)

    # Если файл не скачан (передаём URL/file_id напрямую), передаём оригинальное имя для моста
    kwargs = {}
    if not media_bytes and data.get("filename"):
        kwargs["filename"] = data.get("filename")

    for i, user_id in enumerate(targets, 1):
        try:
            if message_type == "text":
                await bot.send_message(user_id, message_content)
            elif message_type == "photo":
                await bot.send_photo(user_id, current_media, caption=caption, **kwargs)
            elif message_type == "video":
                await bot.send_video(user_id, current_media, caption=caption, **kwargs)
            elif message_type == "document":
                await bot.send_document(user_id, current_media, caption=caption, **kwargs)
            
            success += 1
            
            # Обновляем прогресс каждые 10 сообщений
            if i % 10 == 0 or i == len(targets):
                await edit_admin_message(
                    bot,
                    call.message.message_id,
                    f"🚀 Рассылка в процессе...\n\n"
                    f"📊 Прогресс: {i}/{len(targets)}\n"
                    f"✅ Успешно: {success}\n"
                    f"❌ Ошибок: {failed}"
                )
            
            await asyncio.sleep(0.05)
            
        except Exception as e:
            failed += 1
            logging.error(f"Ошибка отправки {user_id}: {e}")
    
    # Итоговый отчет + Возврат в главное меню
    query = "SELECT COUNT(*) as count FROM users"
    result_users = await get_data(query)
    total_users = result_users[0]['count'] if result_users else 0

    report = (
        f"✅ Рассылка завершена!\n\n"
        f"📊 Итоги:\n"
        f"• 👥 Всего получателей: {len(targets)}\n"
        f"• ✅ Успешно отправлено: {success}\n"
        f"• ❌ Ошибок: {failed}\n"
        f"• 📨 Тип сообщения: {message_type}\n\n"
        f"🔐 <b>Административная панель</b>\n\n"
        f"👥 Пользователей: {total_users}\n\n"
        f"Выберите действие:"
    )
    
    # Финализируем сообщение с прогрессом
    try:
        await edit_admin_message(
            bot,
            call.message.message_id,
            f"✅ Рассылка завершена!\n📊 Успешно: {success}, Ошибок: {failed}"
        )
    except:
        pass

    # Отправляем НОВОЕ сообщение с админ-панелью
    admin_message = await send_to_admin_topic(
        bot,
        report,
        reply_markup=admin_main_keyboard(),
        parse_mode="HTML"
    )
    if admin_message:
        await state.update_data(admin_message_id=admin_message.message_id)
    
    await state.set_state(AdminState.admin_menu)
    await call.answer()

# ===== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ =====
@admin_router.callback_query(F.data == "admin_manage_users_back", StateFilter(AdminState.managing_users))
async def manage_users(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.set_state(AdminState.managing_users)
    
    # Запрос: общее количество пользователей
    query = "SELECT COUNT(*) as count FROM users"
    result = await get_data(query)
    total_users = result[0]['count'] if result else 0
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Список пользователей", callback_data="admin_users_list")
    builder.button(text="🔙 Назад", callback_data="admin_to_main")
    builder.adjust(1)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"👤 Управление пользователями\n\n"
        f"Всего активных пользователей: {total_users}\n\n"
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )
    await call.answer()

# @admin_router.callback_query(F.data == "admin_manage_users", StateFilter(AdminState.admin_menu))
# async def manage_users(call: CallbackQuery, state: FSMContext, bot: Bot):
#     """Управление пользователями"""
#     await state.set_state(AdminState.managing_users)
    
#     # Запрос: общее количество пользователей
#     query = "SELECT COUNT(*) as count FROM users"
#     result = await get_data(query)
#     total_users = result[0]['count'] if result else 0
    
#     builder = InlineKeyboardBuilder()
#     builder.button(text="📋 Список пользователей", callback_data="admin_users_list")
#     builder.button(text="🔙 Назад", callback_data="admin_to_main")
#     builder.adjust(1)
    
#     await edit_admin_message(
#         bot,
#         call.message.message_id,
#         f"👤 Управление пользователями\n\n"
#         f"Всего активных пользователей: {total_users}\n\n"
#         "Выберите действие:",
#         reply_markup=builder.as_markup()
#     )
    await call.answer()

@admin_router.callback_query(F.data == "admin_users_list", StateFilter(AdminState.managing_users))
async def users_list(call: CallbackQuery, state: FSMContext, bot: Bot):
    query = """
    SELECT u.username, b.name_company, b.square, b.agreement, b.acceptance_certificate
    FROM users u 
    JOIN bussines b ON b.id = u.id_business
    ORDER BY b.name_company
    """
    users = await get_data(query)
    print(users)
    
    if not users:
        await call.answer("Нет пользователей", show_alert=True)
        return
    
    users_text = "👥 Список пользователей:\n\n"
    for i, user in enumerate(users, 1):
        
        if user['username'] is None:
            username = 'Пусто'
        else:
            username = user['username']
        print(username)
        name_company = user['name_company']
        square = user['square']
        agreement = user['agreement']
        acceptance_certificate = user['acceptance_certificate']
        
        users_text += f"Название организации/арендатора: {name_company}\n"
        if username == 'Пусто':
            users_text += f"|——имя пользователя: Пусто\n"
        else:
            users_text += f"|——имя пользователя: @{username}\n"
        users_text += f"|——Площадь: {square}\n"
        users_text += f"|——Номер договора: {agreement}\n"
        users_text += f"|——Акт п/п: {acceptance_certificate}\n\n"

    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="admin_manage_users_back")
    builder.adjust(1)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        users_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await call.answer()







async def get_companies_from_db() -> List[Dict]:
    try:
        query = "SELECT id, name_company FROM Bussines ORDER BY name_company"
        records_list = await get_data(query)
        
        companies = []
        if records_list:
            for record in records_list:
                companies.append({
                    'id': record['id'],
                    'name': record['name_company']
                })
        return companies
    except Exception as e:
        print(f"Ошибка при получении компаний из БД: {e}")
        return []

async def get_company_details(company_id: int) -> Dict:
    """Получает подробную информацию о компании по ID"""
    try:
        query = """
        SELECT b.*, fdb.name as form_name, toa.name as activity_name
        FROM Bussines b
        LEFT JOIN form_of_doing_business fdb ON b.id_form = fdb.id
        LEFT JOIN Type_of_Activity toa ON b.id_type_of_activity = toa.id
        WHERE b.id = $1
        """
        records_list = await get_data(query, company_id)
        
        if records_list and len(records_list) > 0:
            return records_list[0]
        return {}
    except Exception as e:
        print(f"Ошибка при получении деталей компании: {e}")
        return {}

async def get_business_forms():
    """Получает список форм бизнеса для выбора при добавлении"""
    try:
        query = "SELECT id, name FROM form_of_doing_business ORDER BY name"
        records_list = await get_data(query)
        return records_list
    except Exception as e:
        print(f"Ошибка при получении форм бизнеса: {e}")
        return []

async def get_activity_types():
    """Получает список видов деятельности для выбора при добавлении"""
    try:
        query = "SELECT id, name FROM Type_of_Activity ORDER BY name"
        records_list = await get_data(query)
        return records_list
    except Exception as e:
        print(f"Ошибка при получении видов деятельности: {e}")
        return []

# ========== КЛАВИАТУРЫ ==========

async def create_companies_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком компаний из БД"""
    companies = await get_companies_from_db()
    keyboard = []
    
    if not companies:
        # Если компаний нет, показываем только кнопку добавления
        keyboard.extend([
            [InlineKeyboardButton(text="➕ Добавить компанию", callback_data="add_company")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_menu_cb_go")]
        ])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    for company in companies:
        button = InlineKeyboardButton(
            text=company['name'],style="primary",
            callback_data=f"company:{company['id']}"
        )
        keyboard.append([button])
    
    keyboard.extend([
        [InlineKeyboardButton(text="➕ Добавить компанию",style="success", callback_data="add_company")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_menu_cb_go")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def delete_or_no_business(company_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да",style="danger", callback_data=f"yesdeletecomp_{company_id}"),
            InlineKeyboardButton(text="Нет",style="success", callback_data=f"dontdeletecomp_{company_id}")
        ],
    ])

async def create_company_actions_keyboard(company_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"editcomp_{company_id}"),
            InlineKeyboardButton(text="🗑️ Удалить",style="danger", callback_data=f"deletecomp_{company_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="back_to_list")]
    ])

async def create_edit_choice_keyboard(company_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Наименование", callback_data=f"edit_name:{company_id}"),
            InlineKeyboardButton(text="Площадь", callback_data=f"edit_square:{company_id}")
        ],
        [
            InlineKeyboardButton(text="Ставка", callback_data=f"edit_bid:{company_id}"),
            InlineKeyboardButton(text="Акт п/п", callback_data=f"edit_acceptance:{company_id}")
        ],
        [
            InlineKeyboardButton(text="Договор", callback_data=f"edit_agreement:{company_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"company:{company_id}")]
    ])

# ========== ОБРАБОТЧИКИ ==========

@admin_router.callback_query(F.data == "admin_menu_cb_go")
async def admin_menu_users(call: CallbackQuery, state: FSMContext):
    from main import bot
    await state.set_state(AdminState.admin_menu)
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"🔐 В меню администратора",
        reply_markup=admin_main_keyboard()
    )
    await call.answer()

@admin_router.callback_query(F.data == "admin_manage_users")
async def admin_manage_users(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.company_list)
    
    companies = await get_companies_from_db()
    
    if not companies:
        text = "👑 <b>Админ-панель: Управление компаниями</b>\n\n📭 <i>Компаний пока нет</i>\n\nДобавьте первую компанию:"
    else:
        text = "👑 <b>Админ-панель: Управление компаниями</b>\n\nВыберите компанию для управления:"
    
    keyboard = await create_companies_keyboard()
    
    await callback.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@admin_router.callback_query(F.data == "back_to_list")
async def handle_back_to_list(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.company_list)
    
    companies = await get_companies_from_db()
    
    if not companies:
        text = "👑 <b>Админ-панель: Управление компаниями</b>\n\n📭 <i>Компаний пока нет</i>\n\nДобавьте первую компанию:"
    else:
        text = "👑 <b>Админ-панель: Управление компаниями</b>\n\nВыберите компанию для управления:"
    
    keyboard = await create_companies_keyboard()
    
    await callback.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@admin_router.callback_query(F.data.startswith("company:"))
async def company_selected(callback: CallbackQuery, state: FSMContext):
    company_id = int(callback.data.split(":")[1])
    
    company_details = await get_company_details(company_id)
    if not company_details:
        await callback.answer("Компания не найдена!")
        return
    
    # Форматируем информацию о компании
    info_lines = [
        f"👑 <b>Управление компанией</b>\n",
        f"🏢 <b>Название:</b> {company_details.get('name_company', 'не указано')}",
        f"📋 <b>Форма бизнеса:</b> {company_details.get('form_name', 'не указана')}",
        f"📏 <b>Площадь:</b> {company_details.get('square', 'не указана')} кв.м",
        f"💰 <b>Ставка аренды:</b> {company_details.get('bid', 'не указана')} руб",
        f"📄 <b>Номер договора:</b> {company_details.get('agreement', 'не указан')}",
        f"📅 <b>Дата завершения договора:</b> {company_details.get('contract_end_date', 'не указана')}",
        f"📋 <b>Акт приема-передачи:</b> {company_details.get('acceptance_certificate', 'не указан')}",
        f"📞 <b>Телефон:</b> {company_details.get('phone', 'не указан')}",
        f"👤 <b>Генеральный директор:</b> {company_details.get('director_name', 'не указан')}",
        f"🏢 <b>Вид деятельности:</b> {company_details.get('activity_name', 'не указан')}"
    ]
    
    keyboard = await create_company_actions_keyboard(company_id)
    
    await callback.message.edit_text(
        text="\n".join(info_lines),
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.company_action)
    await callback.answer()

@admin_router.callback_query(F.data.startswith("editcomp_"))
async def edit_company(callback: CallbackQuery, state: FSMContext):
    company_id = int(callback.data.split("_")[1])
    
    company_details = await get_company_details(company_id)
    if not company_details:
        await callback.answer("Компания не найдена!")
        return
    
    keyboard = await create_edit_choice_keyboard(company_id)
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование компании</b>\n\n"
        f"Выберите параметр для редактирования <b>{company_details.get('name_company', 'Компания')}</b>:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.edit_param)
    await callback.answer()

@admin_router.callback_query(F.data.startswith("edit_"))
async def edit_param_selected(callback: CallbackQuery, state: FSMContext):
    try:
        action_part, company_id_str = callback.data.split(":")
        company_id = int(company_id_str)
    except ValueError:
        await callback.answer("Ошибка формата!")
        return
    
    param_map = {
        "edit_name": ("наименование", "name_company"),
        "edit_square": ("площадь", "square"), 
        "edit_bid": ("ставку аренды", "bid"),
        "edit_agreement": ("номер договора", "agreement"),
        "edit_contract_end": ("дату завершения договора", "contract_end_date"),
        "edit_acceptance": ("акт приема-передачи", "acceptance_certificate"),
        "edit_phone": ("телефон", "phone"),
        "edit_director": ("ФИО ген директора", "director_name")
    }
    
    if action_part not in param_map:
        await callback.answer("Неизвестный параметр!")
        return
    
    param_name, param_key = param_map[action_part]
    
    company_details = await get_company_details(company_id)
    current_value = company_details.get(param_key, 'не установлено')
    
    await state.update_data(
        edit_company_id=company_id,
        edit_param_key=param_key,
        edit_param_name=param_name,
        edit_message_id=callback.message.message_id
    )
    
    await callback.message.edit_text(
        f"✏️ Введите новое значение для <b>{param_name}</b>:\n\n"
        f"Текущее значение: <code>{current_value}</code>\n\n"
        f"<i>Отправьте новое значение в ответе:</i>",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@admin_router.message(AdminState.edit_param)
async def process_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    company_id = data.get("edit_company_id")
    param_key = data.get("edit_param_key")
    param_name = data.get("edit_param_name")
    edit_message_id = data.get("edit_message_id")
    
    if not all([company_id, param_key]):
        await message.edit_text("Ошибка данных! Попробуйте снова.")
        await state.clear()
        return
    
    new_value = message.text.strip()
    if param_key == 'name_company':
        await new_data_insert('UPDATE Bussines SET name_company = $1 WHERE id = $2', new_value, company_id)
    elif param_key == 'square':
        await new_data_insert('UPDATE Bussines SET square = $1 WHERE id = $2', new_value, company_id)
    elif param_key == 'bid':
        await new_data_insert('UPDATE Bussines SET bid = $1 WHERE id = $2', new_value, company_id)
    elif param_key == 'agreement':
        await new_data_insert('UPDATE Bussines SET agreement = $1 WHERE id = $2', new_value, company_id)
    elif param_key == 'contract_end_date':
        await new_data_insert('UPDATE Bussines SET end_date_agreement = $1 WHERE id = $2', new_value, company_id)
    elif param_key == 'acceptance_certificate':
        await new_data_insert('UPDATE Bussines SET acceptance_certificate = $1 WHERE id = $2', new_value, company_id)
    # elif param_key == 'phone':
    #     await new_data_insert('UPDATE Bussines SET {param_key} = $1 WHERE id = $2', new_value, company_id)
    # elif param_key == 'director_name':

    #     await new_data_insert('UPDATE Bussines SET {param_key} = $1 WHERE id = $2', new_value, company_id)
    # "edit_name": ("наименование", "name_company"),
    #     "edit_square": ("площадь", "square"), 
    #     "edit_bid": ("ставку аренды", "bid"),
    #     "edit_agreement": ("номер договора", "agreement"),
    #     "edit_contract_end": ("дату завершения договора", "acceptance_certificate"),
    #     "edit_acceptance": ("акт приема-передачи", "contract_date"),
    #     "edit_phone": ("телефон", "phone"),
    #     "edit_director": ("ФИО ген директора", "director_name")
    # Здесь будет ваш код UPDATE в БД
    # query = f"UPDATE Bussines SET {param_key} = $1 WHERE id = $2"
    # await get_data(query, new_value, company_id)
    # await new_data_insert('UPDATE Bussines SET {param_key} = $1 WHERE id = $2', new_value, company_id)
    try:
        await message.delete()
    except:
        pass
    
    # Возвращаем к управлению компанией
    await state.set_state(AdminState.company_action)
    
    company_details = await get_company_details(company_id)
    info_lines = [
        f"✅ <b>Параметр обновлен!</b>\n",
        f"🏢 <b>Название:</b> {company_details.get('name_company', 'не указано')}",
        f"📋 <b>Форма бизнеса:</b> {company_details.get('form_name', 'не указана')}",
        f"📏 <b>Площадь:</b> {company_details.get('square', 'не указана')} кв.м",
        f"💰 <b>Ставка аренды:</b> {company_details.get('bid', 'не указана')} руб",
        f"📄 <b>Номер договора:</b> {company_details.get('agreement', 'не указан')}",
        f"📅 <b>Дата завершения договора:</b> {company_details.get('contract_end_date', 'не указана')}",
        f"📋 <b>Акт приема-передачи:</b> {company_details.get('acceptance_certificate', 'не указан')}",
        f"📞 <b>Телефон:</b> {company_details.get('phone', 'не указан')}",
        f"👤 <b>Генеральный директор:</b> {company_details.get('director_name', 'не указан')}"
    ]
    
    keyboard = await create_company_actions_keyboard(company_id)
    
    from main import bot
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=edit_message_id,
        text="\n".join(info_lines),
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

@admin_router.callback_query(F.data.startswith('yesdeletecomp_'))
@admin_router.callback_query(F.data.startswith('dontdeletecomp_'))
async def delete_company_check(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    # Формат: yesdeletecomp_{company_id} или dontdeletecomp_{company_id}
    company_id = int(data.split('_')[1])

    if data.startswith('yesdeletecomp_'):
        company_details = await get_company_details(company_id)
        if not company_details:
            await callback.answer("Компания не найдена!")
            return

        company_name = company_details.get('name_company', 'Компания')

        # Удаляем из Excel (не в транзакции — файловые операции)
        try:
            sheet_name = await get_sheet_name_bs(company_id)
            await delete_sheet_in_excel(sheet_name)
            await delete_in_excel(company_name)
        except Exception as e:
            logging.error(f"Ошибка удаления из Excel: {e}")

        # Удаляем из БД единой транзакцией
        conn = None
        try:
            conn = await asyncpg.connect(config.db_connection)
            async with conn.transaction():
                await conn.execute('DELETE FROM us_readings WHERE business_id = $1', company_id)
                await conn.execute('DELETE FROM business_documents WHERE id_business = $1', company_id)
                await conn.execute('DELETE FROM users WHERE id_business = $1', company_id)
                await conn.execute('DELETE FROM bussines WHERE id = $1', company_id)
        except Exception as e:
            logging.error(f"Ошибка удаления компании {company_id} из БД: {e}")
            await callback.message.edit_text(
                text=f"❌ <b>Ошибка удаления</b>\n\nНе удалось удалить компанию <b>{company_name}</b>.\n\n"
                     f"<i>Причина: {e}</i>\n\nПопробуйте снова или обратитесь к администратору.",
                parse_mode=ParseMode.HTML
            )
            await callback.answer()
            return
        finally:
            if conn:
                await conn.close()

        await state.set_state(AdminState.company_list)
        keyboard = await create_companies_keyboard()

        companies = await get_companies_from_db()
        if not companies:
            text = f"🗑️ <b>Компания удалена</b>\n\nКомпания <b>{company_name}</b> была удалена.\n\n👑 <b>Админ-панель: Управление компаниями</b>\n\n📭 <i>Компаний пока нет</i>\n\nДобавьте новую компанию:"
        else:
            text = f"🗑️ <b>Компания удалена</b>\n\nКомпания <b>{company_name}</b> была удалена.\n\n👑 <b>Админ-панель: Управление компаниями</b>\n\nВыберите компанию для управления:"

        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await callback.answer()
    else:
        keyboard = await create_companies_keyboard()
        await callback.message.edit_text(
            text='Админ-панель: Управление компаниями\nНе удалили компанию, какое действие хотите совершить?',
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await callback.answer()
    

@admin_router.callback_query(F.data.startswith("deletecomp_"))
async def delete_company(callback: CallbackQuery, state: FSMContext):
    company_id = int(callback.data.split("_")[1])
    
    company_details = await get_company_details(company_id)
    if not company_details:
        await callback.answer("Компания не найдена!")
        return
    
    company_name = company_details.get('name_company', 'Компания')
    keyboard = await delete_or_no_business(company_id=company_id)
    companies = await get_companies_from_db()
    if not companies:
        text = f"Точно хотите удалить компанию {company_name}?"
    else:
        text = f"Точно хотите удалить компанию {company_name}?"
    
    await callback.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@admin_router.callback_query(F.data == "add_company")
async def add_company_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(
        new_company={},
        add_step=1,
        add_message_id=callback.message.message_id
    )
    
    await callback.message.edit_text(
        "➕ <b>Добавление ИНН - Шаг 1/11</b>\n\n"  # Изменил на 11 шагов
        "Введите <b>ИНН</b>:",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.add_company)
    await callback.answer()


@admin_router.message(AdminState.add_company)
async def process_add_company(message: Message, state: FSMContext, bot: Bot):
    # Удаляем сообщение пользователя сразу, до обработки
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except:
        pass
        
    from handlers.excel_tg_test import copy_sheet_safe, safe_add_to_excel
    from handlers.admin_meter_handlers import temp_meter_data
    data = await state.get_data()
    current_step = data.get("add_step", 1)
    new_company = data.get("new_company", {})
    add_message_id = data.get("add_message_id")
    
    # Защита от сообщений без текста (стикеры, фото и т.д.)
    if not message.text:
        return
        
    new_value = message.text.strip()
    
    # Шаги 1-9 (текстовые поля)
    if 1 <= current_step <= 9:
        steps = {
            1: ("ИНН", "inn", "Введите <b>площадь</b> (в кв.м):") ,
            2: ("Площадь", "square", "Введите <b>ставку аренды</b> (руб):"),
            3: ("Ставка аренды", "bid", "Введите <b>номер договора</b>:"),
            4: ("Номер договора", "agreement", "Введите <b>дату завершения договора</b> (ДД.ММ.ГГГГ):"),
            5: ("Дата завершения", "contract_end_date", "Введите <b>дату акта приема-передачи</b> (ДД.ММ.ГГГГ):"),
            6: ("Акт приема-передачи", "acceptance_certificate", "Введите <b>телефон</b> компании:"),
            7: ("Телефон", "phone", "Введите <b>Наименование</b> компании:"),
            8: ("Наименование компании", "name_company", "Введите ФИО генерального директора"),
            9: ("ФИО ген директора", "director_name", None)
        }
        
        field_display, field_key, next_question = steps[current_step]

        # Валидации по шагам
        if current_step == 2:  # площадь
            try:
                float(new_value)
            except ValueError:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=add_message_id,
                    text=f"<b>Шаг 2/11</b> - Введите <b>площадь</b> (в кв.м):\n\n"
                         f"❌ Площадь должна быть числом (можно с десятичной частью).\n"
                         f"Примеры: 100, 150.5, 75.2\n\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                return
        
        elif current_step == 3:  # ставка
            try:
                float(new_value)
            except ValueError:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=add_message_id,
                    text=f"<b>Шаг 3/11</b> - Введите <b>ставку аренды</b> (руб):\n\n"
                         f"❌ Ставка должна быть числом (можно с десятичной частью).\n"
                         f"Примеры: 1000, 1500.50, 2000\n\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                return
        
        elif current_step == 5:  # дата завершения
            try:
                input_date = datetime.strptime(new_value, "%d.%m.%Y")
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

                if input_date < today:
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=add_message_id,
                        text=f"<b>Шаг 5/11</b> - Введите <b>дату завершения договора</b> (ДД.ММ.ГГГГ):\n\n"
                             f"❌ Дата должна быть больше сегодняшней.\n"
                             f"Сегодня: {today.strftime('%d.%m.%Y')}\n\n"
                             f"Попробуйте снова:",
                        parse_mode=ParseMode.HTML
                    )
                    return
            except ValueError:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=add_message_id,
                    text=f"<b>Шаг 5/11</b> - Введите <b>дату завершения договора</b> (ДД.ММ.ГГГГ):\n\n"
                         f"❌ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ\n"
                         f"Например: 31.12.2024\n\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                return
        
        elif current_step == 6:  # дата акта
            try:
                datetime.strptime(new_value, "%d.%m.%Y")
            except ValueError:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=add_message_id,
                    text=f"<b>Шаг 6/11</b> - Введите <b>дату акта приема-передачи</b> (ДД.ММ.ГГГГ):\n\n"
                         f"❌ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ\n"
                         f"Например: 31.12.2024\n\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                return
        
        elif current_step == 1:  # ИНН
            check_in_existing_user = check_word_in_excel_file(new_value)
            error_text = None
            if not new_value.isdigit():
                error_text = "❌ ИНН должен содержать только цифры."
            elif len(new_value) not in [10, 12]:
                error_text = "❌ ИНН должен содержать 10 или 12 цифр."

            if error_text:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=add_message_id,
                    text=f"<b>Шаг 1/11</b> - Введите <b>ИНН</b> компании:\n\n"
                         f"{error_text}\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                return
            if check_in_existing_user:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=add_message_id,
                    text=f"<b>Шаг 1/11</b> - Введите <b>ИНН</b> компании:\n\n"
                         f"Данный ИНН уже есть в системе\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                return
        elif current_step == 9:  # ФИО
            error_text = None
            fio_parts = new_value.split()
            if len(fio_parts) < 3:
                error_text = "❌ Введите полное ФИО (минимум 3 слова). Пример: Иванов Иван Иванович"
            elif not re.match(r'^[а-яА-ЯёЁ\s\-]+$', new_value):
                error_text = "❌ ФИО должно содержать только буквы, пробелы и дефисы."

            if error_text:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=add_message_id,
                    text=f"<b>Шаг 9/11</b> - Введите <b>ФИО генерального директора</b>:\n\n"
                         f"{error_text}\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                return

        # Сохраняем значение
        new_company[field_key] = new_value
        
        # Если это последний текстовый шаг (ФИО)
        if current_step == 9:
            # После ФИО показываем формы бизнеса
            business_forms = await get_business_forms()
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=form['name'] if hasattr(form, '__getitem__') else form.name,
                    callback_data=f"form:{form['id'] if hasattr(form, '__getitem__') else form.id}"
                )] for form in business_forms
            ] + [[InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_list")]])

            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=add_message_id,
                text=f"✅ <b>{field_display}</b> сохранено!\n\n"
                     f"<b>Шаг 10/11</b> - Выберите <b>форму бизнеса</b>:",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
            await state.update_data(new_company=new_company, add_step=10)
        else:
            # Переход к следующему шагу
            await state.update_data(new_company=new_company, add_step=current_step + 1)

            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=add_message_id,
                text=f"✅ <b>{field_display}</b> сохранено!\n\n"
                     f"<b>Шаг {current_step + 1}/11</b> - {next_question}",
                parse_mode=ParseMode.HTML
            )
    
    # Финальный шаг - ввод вида деятельности
    elif current_step == 10:
        new_company['activity_type'] = new_value
        name_company = new_company.get('name_company')
        activity_type = new_company.get('activity_type')
        id_form_doing = new_company.get('id_form')
        square = float(new_company.get('square'))
        bid = float(new_company.get('bid'))
        agreement = new_company.get('agreement')
        try:
            acceptance_certificate = datetime.strptime(new_company.get('acceptance_certificate', ''), "%d.%m.%Y").date()
            
        except (ValueError, TypeError):
            end_agreement = None  
            acceptance_certificate = None
        end_agreement = new_company.get('contract_end_date')
        phone = new_company.get('phone')
        inn = new_company.get('inn')
        sfp_general_direcotr = new_company.get('director_name')
        gen_dir_list = sfp_general_direcotr.split(' ')
        # ВЫВОД ИНФЫ
        company_info = f"""
            📋 <b>ДАННЫЕ НОВОЙ КОМПАНИИ:</b>

            🏢 <b>Наименование:</b> {name_company}
            📋 <b>Форма бизнеса ID:</b> {id_form_doing}
            📏 <b>Площадь:</b> {square} кв.м
            💰 <b>Ставка аренды:</b> {bid} руб
            📄 <b>Номер договора:</b> {agreement}
            📅 <b>Дата завершения:</b> {end_agreement}
            📋 <b>Акт приема-передачи:</b> {acceptance_certificate}
            📞 <b>Телефон:</b> {phone}
            🔢 <b>ИНН:</b> {inn}
            👤 <b>Генеральный директор:</b> {sfp_general_direcotr}
            🏢 <b>Вид деятельности:</b> {activity_type}
        """
        
        await new_data_insert('INSERT INTO type_of_activity (name) VALUES ($1) ON CONFLICT (name) DO NOTHING', activity_type)
        records = await get_data('SELECT id FROM type_of_activity WHERE name = $1 LIMIT 1', activity_type)
        records_fod = await get_data('SELECT name FROM form_of_doing_business WHERE id = $1',id_form_doing)
        id_toas = [record['id'] for record in records]
        id_toa = id_toas[0]
        name_fods = [record['name'] for record in records_fod]
        name_fod = name_fods[0]
        
        # ДОБАВИТЬ ЛОГИКУ СОЗДАНИЯ КОПИИ EXCEL листа
        list_name = f'K{square}'
        sfp_list = str(sfp_general_direcotr).split(' ')
        list_data=[agreement, inn, name_fod, name_company, activity_type, square, list_name, acceptance_certificate, sfp_list[0], sfp_list[1], sfp_list[2], end_agreement, phone]
        await copy_sheet_safe(list_name)
        await safe_add_to_excel(list_data)
        await new_data_insert('INSERT INTO bussines(name_company, id_form, square, bid, acceptance_certificate, agreement, end_date_agreement, id_type_of_activity, sheet_name,surname,first_name,patronymic) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)', 
                            name_company, id_form_doing, square, bid, acceptance_certificate, agreement, end_agreement, id_toa, list_name,gen_dir_list[0],gen_dir_list[1],gen_dir_list[2])
        

        # ========== ИНТЕГРАЦИЯ С НОВЫМ РОУТЕРОМ ==========
        
        records_ids = await get_data('SELECT id FROM bussines WHERE name_company = $1 AND square = $2',name_company,square)
        for business in records_ids:
            company_id = business['id']
        # Очищаем возможные старые данные для этой компании
        if company_id in temp_meter_data:
            del temp_meter_data[company_id]
        
        # Сохраняем данные в state для возврата
        await state.update_data(
            company_id=company_id,
            return_text=company_info,
            return_message_id=add_message_id
        )
        
        # Клавиатура с вопросом о счетчиках
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Я", callback_data=f"meter_filler_admin")],
            [InlineKeyboardButton(text="🏢 Арендатор", callback_data="meter_filler_tenant")],
        ])
        
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=add_message_id,
            text="✅ <b>Компания успешно создана!</b>\n\n"
                 "Теперь нужно добавить номера счетчиков:\n"
                 "• ❄️ Холодная вода\n"
                 "• 🔥 Горячая вода\n"
                 "• ⚡️ Электричество\n\n"
                 "<i>Номера можно будет изменить позже в настройках компании.</i>\n\n"
                 "Кто будет заполнять номера?",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        
        # Устанавливаем состояние выбора заполнителя (из вашего admin_states.py)
        await state.set_state(AdminState.meter_filler_choice)
        
        # ========== КОНЕЦ ИНТЕГРАЦИИ ==========

        # await state.set_state(AdminState.company_list)
        # keyboard = await create_companies_keyboard()
        
        # from main import bot
        # await bot.edit_message_text(
        #     chat_id=message.chat.id,
        #     message_id=add_message_id,
        #     text=company_info,
        #     reply_markup=keyboard,
        #     parse_mode=ParseMode.HTML
        # )
        
        # # Очищаем состояние
        # await state.clear()


@admin_router.callback_query(F.data.startswith("form:"))
async def select_business_form(callback: CallbackQuery, state: FSMContext):
    form_id = int(callback.data.split(":")[1])
    
    data = await state.get_data()
    new_company = data.get("new_company", {})
    add_message_id = data.get("add_message_id")
    
    new_company['id_form'] = form_id
    
    from main import bot
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=add_message_id,
        text=f"✅ <b>Форма бизнеса</b> выбрана!\n\n"
             f"<b>Шаг 10/10</b> - Введите <b>вид деятельности</b>:",
        parse_mode=ParseMode.HTML
    )
    
    await state.update_data(new_company=new_company, add_step=10)  # меняем на 10
    await callback.answer()






# await new_data_insert('INSERT INTO type_of_activity (name) VALUES ($1)) ON CONFLICT (name) DO NOTHING', activity_type)
#         records = await get_data('SELECT id FROM type_of_activity WHERE name = $1 LIMIT 1',activity_type)
#         id_toa = {rec['id'] for rec in records}
#         # ДОБАВИТЬ ЛОГИКУ СОЗДАНИЯ КОПИИ EXCEL листа
#         list_name = f'K{square}'
#         await copy_sheet_safe(list_name)
#         await new_data_insert('INSERT INTO bussines(name_company, id_form, square, bid, acceptance_certificate, agreement, end_date_agreement, id_type_of_activity) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)', name_company, id_form_doing, square, bid, acceptance_certificate, agreement, end_agreement, id_toa)
#         await state.set_state(AdminState.company_list)

@admin_router.callback_query(F.data.startswith("activity:"))
async def select_activity_type(callback: CallbackQuery, state: FSMContext):
    activity_id = int(callback.data.split(":")[1])
    
    data = await state.get_data()
    new_company = data.get("new_company", {})
    
    new_company['id_type_of_activity'] = activity_id
    
    await state.update_data(new_company=new_company)
    
    # ВЫВОД ВСЕХ ДАННЫХ ДЛЯ СОХРАНЕНИЯ
    company_info = f"""
    📋 <b>ДАННЫЕ ДЛЯ СОХРАНЕНИЯ В БД:</b>
    
    <b>Наименование компании:</b> {new_company.get('name_company')}
    <b>Форма бизнеса ID:</b> {new_company.get('id_form')}
    <b>Площадь:</b> {new_company.get('square')} кв.м
    <b>Ставка аренды:</b> {new_company.get('bid')} руб
    <b>Номер договора:</b> {new_company.get('agreement')}
    <b>Дата завершения договора:</b> {new_company.get('contract_end_date')}
    <b>Акт приема-передачи:</b> {new_company.get('acceptance_certificate')}
    <b>Телефон:</b> {new_company.get('phone')}
    <b>Генеральный директор:</b> {new_company.get('director_name')}
    <b>Вид деятельности ID:</b> {new_company.get('id_type_of_activity')}
    """
    
    # Здесь будет ваш код сохранения в БД
    # insert_query = """
    # INSERT INTO Bussines 
    # (name_company, square, bid, agreement, contract_end_date, 
    #  acceptance_certificate, phone, director_name, id_form, id_type_of_activity)
    # VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    # """
    # await get_data(insert_query,
    #     new_company['name_company'],
    #     new_company['square'],
    #     new_company['bid'],
    #     new_company['agreement'],
    #     new_company['contract_end_date'],
    #     new_company['acceptance_certificate'],
    #     new_company['phone'],
    #     new_company['director_name'],
    #     new_company['id_form'],
    #     new_company['id_type_of_activity']
    # )
    
    await state.set_state(AdminState.company_list)
    keyboard = await create_companies_keyboard()
    
    companies = await get_companies_from_db()
    if not companies:
        text = f"✅ <b>Компания добавлена!</b>\n\nКомпания <b>{new_company['name_company']}</b> успешно добавлена.\n\n👑 <b>Админ-панель: Управление компаниями</b>\n\n📭 <i>Компаний пока нет</i>\n\nДобавьте новую компанию:"
    else:
        text = f"✅ <b>Компания добавлена!</b>\n\nКомпания <b>{new_company['name_company']}</b> успешно добавлена.\n\n👑 <b>Админ-панель: Управление компаниями</b>\n\nВыберите компанию для управления:"
    
    # Выводим информацию о собранных данных перед сохранением
    await callback.message.edit_text(
        text=company_info + "\n\n" + text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    
    await callback.answer()

@admin_router.callback_query(F.data == "back_to_forms")
async def back_to_forms(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    business_forms = data.get("business_forms", [])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=form['name'], callback_data=f"form:{form['id']}")]
        for form in business_forms
    ] + [[InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_list")]])
    
    await callback.message.edit_text(
        "Выберите <b>форму бизнеса</b>:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()



    
# ===== ОБРАБОТЧИКИ КОМАНД =====
async def tenants_keyboard(list_ended_tenant, page: int = 0):
    print(f'Проверка при вызове функции {list_ended_tenant}')
    query = """
    SELECT b.name_company, b.id
    FROM bussines b 
    ORDER BY b.name_company
    """
    users = await get_data(query) 

    tenants_per_page = 8
    
    # Если арендаторов нет
    if not users:
        buttons = [[InlineKeyboardButton(text="❌ Нет арендаторов", callback_data="no_tenants")]]
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_services")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Пагинация
    start_idx = page * tenants_per_page
    end_idx = start_idx + tenants_per_page
    current_tenants = users[start_idx:end_idx]
    
    buttons = []
    if not list_ended_tenant:
        for tenant in current_tenants:
            buttons.append([
                InlineKeyboardButton(
                    text=tenant['name_company'],
                    callback_data=f"tenant_{tenant['id']}"
                )
            ])
    else:
        for tenant in current_tenants:
            if tenant['id'] in list_ended_tenant:
                buttons.append([
        InlineKeyboardButton(
            text=f"✅ {tenant['name_company']} (внесено)",
            callback_data=f"tenant_done_{tenant['id']}"  # или просто заглушка
        )
    ])
            else:
                buttons.append([
                    InlineKeyboardButton(
                        text=tenant['name_company'],
                        callback_data=f"tenant_{tenant['id']}"
                    )
                ])
        
    # Кнопки пагинации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"tenants_page_{page-1}"))
    if end_idx < len(users):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"tenants_page_{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Кнопка назад
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_services")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_readings_keyboard(tenant_id: int):
    """Клавиатура подтверждения показаний"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Сохранить", callback_data=f"savetenant_readings_{tenant_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edittenant_readings_{tenant_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_tenant_selection")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Обработчики
@admin_router.callback_query(F.data == "admin_submit_readings")
async def admin_submit_readings(call: CallbackQuery, state: FSMContext):
    from main import bot
    await state.set_state(AdminState.choosing_service)
    
    await call.answer()

    await edit_admin_message(
        bot,
        call.message.message_id,
        "📝 Подача показаний\n\n"
        "Выберите тип услуги:",
        reply_markup=service_keyboard(),
        parse_mode="HTML"
    )
    


@admin_router.callback_query(F.data == "back_to_admin_menu", StateFilter(AdminState.choosing_service))
@admin_router.callback_query(F.data == "back_to_admin_menu", StateFilter(AdminState.choosing_service))
async def back_to_admin_menu(call: CallbackQuery, state: FSMContext):
    from main import bot
    
    await state.set_state(AdminState.admin_menu)
    await edit_admin_message(
        bot,
        call.message.message_id,
        "👨‍💼 Панель администратора",
        reply_markup=admin_main_keyboard(),
        parse_mode="HTML"
    )
    await call.answer()


@admin_router.callback_query(F.data == "back_to_services", StateFilter(AdminState.selecting_tenant))
async def back_to_services_handler(call: CallbackQuery, state: FSMContext):
    from main import bot
    await state.set_state(AdminState.choosing_service)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        "📝 Подача показаний\n\n"
        "Выберите тип услуги:",
        reply_markup=service_keyboard(),
        parse_mode="HTML"
    )
    await call.answer()

@admin_router.callback_query(F.data == "service_heat", StateFilter(AdminState.choosing_service))
async def service_heat_handler(call: CallbackQuery, state: FSMContext):
    from main import bot
    await call.answer()
    await state.set_state(AdminState.selecting_tenant)
    await state.update_data(service_type="heat", page=0)
    new_data = await state.get_data()
    new_items = new_data.get('list_tenant', [])
    keyboard = await tenants_keyboard(new_items,page=0)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        "🔥 Отопление\n\n"
        "Выберите арендатора для подачи показаний:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    


@admin_router.callback_query(F.data == "service_common", StateFilter(AdminState.choosing_service))
async def service_common_handler(call: CallbackQuery, state: FSMContext):
    from main import bot
    global collected_data
    # collected_data = {}  # Сбрасываем предыдущие данные
    
    await state.set_state(AdminState.choosing_type)
    await edit_admin_message(
        bot,
        call.message.message_id,
        "📊 Подача показаний\n\n"
        "Выберите тип показаний для внесения:",
        reply_markup=type_keyboard(),
        parse_mode="HTML"
    )
    await call.answer()


@admin_router.callback_query(F.data.startswith("tenants_page_"), StateFilter(AdminState.selecting_tenant))
async def tenants_pagination(call: CallbackQuery, state: FSMContext):
    from main import bot
    page = int(call.data.split("_")[2])
    await state.update_data(page=page)
    new_data = await state.get_data()
    new_items = new_data.get('list_tenant', [])
    keyboard = await tenants_keyboard(new_items,page=page)
    await call.message.edit_text(text="🔥 Отопление\n\n"
        "Выберите арендатора для подачи показаний:",
        reply_markup=keyboard,
        parse_mode="HTML")
    # await edit_admin_message(
    #     bot,
    #     call.message.message_id,
    #     "🔥 Отопление\n\n"
    #     "Выберите арендатора для подачи показаний:",
    #     reply_markup=keyboard,
    #     parse_mode="HTML"
    # )
    await call.answer()

@admin_router.callback_query(F.data.startswith("admin_edit_tariff_"), StateFilter(AdminState.editing_data))
async def edit_tariff_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Начать редактирование тарифа холодной воды"""
    edit_type = call.data.replace("admin_edit_tariff_", "")
    
    global collected_data
    if edit_type not in collected_data:
        await call.answer("Данные не найдены!", show_alert=True)
        await show_edit_menu_from_state(call, state, bot)
        return
    
    await state.update_data(
        edit_type=edit_type,
        editing_field="tariff"
    )
    
    # Используем отдельное состояние для редактирования
    await state.set_state(AdminState.waiting_for_tariff_edit)
    
    current_tariff = collected_data.get(edit_type, {}).get('tariff', '—')
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"✏️ Редактирование тарифа\n\n"
        f"Текущее значение: {current_tariff} руб./м³\n\n"
        f"Введите новый тариф (в рублях за м³):\n"
        f"(например: 45.50)",
        reply_markup=cancel_keyboard(with_edit_option=True),
        parse_mode="HTML"
    )
    await call.answer()


# Обработчик для РЕДАКТИРОВАНИЯ тарифа
@admin_router.message(StateFilter(AdminState.waiting_for_tariff_edit))
async def process_tariff_edit_input(message: Message, state: FSMContext, bot: Bot):
    """Обработка введенного тарифа при РЕДАКТИРОВАНИИ"""
    if message.chat.id != ADMIN_CHAT_ID:
        return
    
    raw_text = message.text.replace(",", ".")
    
    try:
        tariff = float(raw_text)
        if tariff < 0:
            raise ValueError
    except ValueError:
        await send_to_admin_topic(
            bot,
            "⚠️ Ошибка ввода\n\n"
            "Пожалуйста, введите корректный тариф (положительное число).",
            reply_markup=cancel_keyboard()
        )
        return
    
    data = await state.get_data()
    edit_type = data.get("edit_type")
    last_msg_id = data.get("last_msg_id")  # Получаем ID последнего сообщения бота
    
    # Сохраняем тариф
    global collected_data
    if edit_type not in collected_data:
        collected_data[edit_type] = {}
    
    collected_data[edit_type]["tariff"] = tariff
    
    # Возвращаемся в меню редактирования
    await state.set_state(AdminState.editing_data)
    
    names = get_type_names()
    label = names.get(edit_type, "")
    
    builder = InlineKeyboardBuilder()
    
    # Для холодной воды - только тариф
    builder.button(text="💰 Редактировать тариф", callback_data=f"admin_edit_tariff_{edit_type}")
    builder.button(text="🔙 Назад к списку", callback_data="admin_edit_menu")
    builder.adjust(1)
    
    type_data = collected_data.get(edit_type, {})
    
    # Пытаемся отредактировать последнее сообщение бота
    if last_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=ADMIN_CHAT_ID,
                message_id=last_msg_id,
                text=f"✅ Тариф обновлен!\n\n"
                     f"✏️ Редактирование показаний {label}\n\n"
                     f"Текущие значения:\n"
                     f"• Тариф: {type_data.get('tariff', '—')} руб./м³\n\n"
                     f"Что вы хотите изменить?",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка редактирования: {e}")
            # Если не получилось отредактировать, отправляем новое сообщение
            new_msg = await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"✅ Тариф обновлен!\n\n"
                     f"✏️ Редактирование показаний {label}\n\n"
                     f"Текущие значения:\n"
                     f"• Тариф: {type_data.get('tariff', '—')} руб./м³\n\n"
                     f"Что вы хотите изменить?",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            await state.update_data(last_msg_id=new_msg.message_id)
    else:
        # Если нет last_msg_id, отправляем новое сообщение
        new_msg = await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"✅ Тариф обновлен!\n\n"
                 f"✏️ Редактирование показаний {label}\n\n"
                 f"Текущие значения:\n"
                 f"• Тариф: {type_data.get('tariff', '—')} руб./м³\n\n"
                 f"Что вы хотите изменить?",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await state.update_data(last_msg_id=new_msg.message_id)
    
    # Удаляем сообщение с вводом
    try:
        await bot.delete_message(ADMIN_CHAT_ID, message.message_id)
    except:
        pass


@admin_router.callback_query(F.data.startswith("tenant_"), StateFilter(AdminState.selecting_tenant))
async def tenant_selected(call: CallbackQuery, state: FSMContext):
    from main import bot
    tenant_id = int(call.data.split("_")[1])
    users = await get_data('SELECT b.name_company, b.id FROM bussines b WHERE b.id = $1',tenant_id) 
    for user in users:
        name_company = user['name_company']
    
    await state.update_data(
        selected_tenant_id=tenant_id,
        selected_tenant_name=name_company if name_company else "Неизвестный"
    )
    
    await state.set_state(AdminState.waiting_for_heat_volume)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"🔥 Отопление - {name_company}\n\n"
        f"Введите показания счетчика отопления (целое число):",
        parse_mode="HTML"
    )
    await call.answer()


@admin_router.message(StateFilter(AdminState.waiting_for_heat_volume))
async def heat_volume_input(message: Message, state: FSMContext, bot: Bot):
    from main import bot
    try:
        volume = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите целое число!\n"
            "Попробуйте еще раз:",
        )
        return
    if len(str(volume))<12:
        await state.update_data(heat_volume=volume)
        await state.set_state(AdminState.waiting_for_heat_amount)
        
        data = await state.get_data()
        tenant_name = data.get('selected_tenant_name', 'Арендатор')
        
        await message.answer(
            f"✅ Показания: {volume}\n\n"
            f"🔥 Отопление - {tenant_name}\n"
            f"Введите сумму с НДС (в рублях):\n"
            f"(например: 1250.75)",
        )
    else:
        await message.answer(
            f"Пожалуйста введите корректное значение"
        )



@admin_router.message(StateFilter(AdminState.waiting_for_heat_amount))
async def heat_amount_input(message: Message, state: FSMContext, bot: Bot):
    """Ввод суммы отопления"""
    try:
        str_len = message.text
        # Пробуем преобразовать в float
        amount = float(message.text.strip().replace(',', '.'))
        # Округляем до 2 знаков
        amount = round(amount, 2)
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректную сумму!\n"
            "Например: 1250.75 или 1250,75",
        )
        return
    if len(str_len)<14:
        await state.update_data(heat_amount=amount)
        
        data = await state.get_data()
        tenant_name = data.get('selected_tenant_name', 'Арендатор')
        tenant_id = data.get('selected_tenant_id')
        volume = data.get('heat_volume')
        
        await state.set_state(AdminState.confirming_readings)
        
        await message.answer(
            f"📊 Проверьте введенные данные:\n\n"
            f"Арендатор: {tenant_name}\n"
            f"Услуга: 🔥 Отопление\n"
            f"Показания: {volume}\n"
            f"Сумма: {amount:.2f} ₽\n\n"
            f"Сохранить или отредактировать?",
            reply_markup=confirm_readings_keyboard(tenant_id)
        )
    else:
        await message.answer('Пожалуйста введите корректное значение')


@admin_router.callback_query(F.data.startswith("savetenant_readings_"), StateFilter(AdminState.confirming_readings))
async def save_readings(call: CallbackQuery, state: FSMContext):
    from main import bot
    from handlers.excel_tg_test import add_tenant_for_user
    import asyncio
    import locale
    from datetime import datetime, timedelta
    
    tenant_id = int(call.data.split("_")[2])
    data = await state.get_data()
    volume = data['heat_volume']
    amount = data['heat_amount']
    
    # Сохраняем показания арендатора
    await add_tenant_for_user(tenant_id, volume=volume, amount=amount)
    
    # Обновляем список обработанных арендаторов
    data = await state.get_data()
    items = data.get('list_tenant', [])
    items.append(tenant_id)
    await state.update_data(list_tenant=items)
    new_data = await state.get_data()
    new_items = new_data.get('list_tenant', [])
    await state.set_state(AdminState.selecting_tenant)
    
    # Получаем список всех арендаторов из БД
    query = """
    SELECT b.id
    FROM bussines b 
    ORDER BY b.name_company
    """
    users_records = await get_data(query) 
    list_ids = []
    for user in users_records:
        list_ids.append(user['id'])
    text_create = ''
    # Если обработаны не все арендаторы
    if sorted(list_ids) != sorted(new_items):
        keyboard = await tenants_keyboard(new_items, page=0)
        await edit_admin_message(
            bot,
            call.message.message_id,
            f"✅ Показания успешно сохранены!\n\n"
            f"🔥 Отопление\n\n"
            f"Выберите следующего арендатора:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await call.answer("Показания сохранены", show_alert=False)
        return

    # ===== ВСЕ АРЕНДАТОРЫ ОБРАБОТАНЫ =====
    global collected_data
    
    # Получаем даты периода
    start_date = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")
    end_date = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    collected_data['heating'] = {'volume': 0, 'amount': 0}

    # Проверяем остальные показатели
    required = ['electro', 'water_cold', 'expl', 'drainage']
    missing = []
    names = {
        'electro': '⚡ Электроэнергия',
        'water_cold': '🚰 Холодная вода',
        'expl': '🏢 Комм. услуги',
        'drainage': '💧 Водоотведение'
    }

    for req in required:
        if req not in collected_data or not collected_data[req]:
            missing.append(names[req])

    # Если не все общие показатели заполнены
    if missing:
        text_create = f"❌ <b>Не все показатели заполнены!</b>\n\nОтсутствуют:\n" + "\n".join(missing)+'\n\n📊 <b>Сбор показателей</b>\n\nВыберите показатель для ввода:'

        await state.set_state(AdminState.collecting_data)
        await edit_admin_message(
            bot,
            call.message.message_id,
            text=text_create,
            reply_markup=admin_main_keyboard()
        )
        return

    # ===== ВСЕ ПОКАЗАТЕЛИ ЗАПОЛНЕНЫ =====
    await state.set_state(AdminState.collecting_data)
    
    # Формируем отчет о собранных данных
    report = "✅ <b>Все показатели собраны!</b>\n\n"
    
    # Отопление
    report += f"🔥 Отопление\n"
    report += f"• Сумма: - руб.\n\n"
    
    # Остальные показатели
    display_names = {
        'electro': '⚡ Электроэнергия',
        'water_cold': '🚰 Холодная вода',
        'expl': '🏢 Комм. услуги',
        'drainage': '💧 Водоотведение'
    }
    
    for req in required:
        if req in collected_data:
            data = collected_data[req]
            label = display_names[req]
            report += f"{label}\n"
            
            if req == 'water_cold':
                report += f"• Тариф: {data.get('tariff', 0)} руб./м³\n\n"
            elif req in ['expl', 'drainage']:
                report += f"• Сумма: {data.get('amount', 0)} руб.\n\n"
            else:  # electro
                report += f"• Объем: {data.get('volume', 0)}\n"
                report += f"• Сумма: {data.get('amount', 0)} руб.\n\n"
    
    # Кнопки для выбора
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Непредвиденные расходы", callback_data="admin_unexpected_expenses")
    builder.button(text="📎 Прикрепить документы", callback_data="admin_attach_documents")
    builder.button(text="✅ Отправить", callback_data="admin_final_save")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        report,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    
    await call.answer("✅ Все показатели собраны!")

# @admin_router.callback_query(F.data.startswith("savetenant_readings_"), StateFilter(AdminState.confirming_readings))
# async def save_readings(call: CallbackQuery, state: FSMContext):
#     from main import bot
#     from handlers.excel_tg_test import add_tenant_for_user
#     from handlers.excel_tg_test import admin_indicators, create_excel, get_volume_and_amount_month, count_tenant_excel,create_word
#     import asyncio
#     tenant_id = int(call.data.split("_")[2])
#     data = await state.get_data()
#     volume=data['heat_volume']
#     amount=data['heat_amount']
#     await add_tenant_for_user(tenant_id,volume=volume,amount=amount)
#     data = await state.get_data()
#     items = data.get('list_tenant', [])
#     items.append(tenant_id)
#     await state.update_data(list_tenant=items)
#     new_data = await state.get_data()
#     new_items = new_data.get('list_tenant', [])
#     await state.set_state(AdminState.selecting_tenant)
    
#     start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%d.%m.%Y")
#     end = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%d.%m.%Y")
#     prev = datetime.now().replace(day=1) - timedelta(days=1)
#     prev_month_name_en = prev.strftime("%B")
#     prev_year = prev.strftime("%Y")
#     try:
#         locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
#         prev_month_name_ru = prev.strftime("%B").capitalize()  # "Январь"
#     except:
#         prev_month_name_ru = prev_month_name_en  # fallback

#     # Полезные комбинации
#     period_str = f"{prev_month_name_ru} {prev_year}"
#     info_list = [end,start,end,period_str]

#     query = """
#     SELECT b.id
#     FROM bussines b 
#     ORDER BY b.name_company
#     """
#     users_records = await get_data(query) 
#     list_ids = []
#     for user in users_records:
#         list_ids.append(user['id'])

#     if sorted(list_ids) == sorted(new_items):
#         global collected_data
#         collected_data['heating'] = {'volume': 0, 'amount': 0}

#         # Проверяем остальные показатели
#         required = ['electro', 'water_cold', 'expl', 'drainage']
#         missing = []
#         names = {
#             'electro': '⚡ Электроэнергия',
#             'water_cold': '🚰 Холодная вода',
#             'expl': '🏢 Комм. услуги',
#             'drainage': '💧 Водоотведение'
#         }

#         for req in required:
#             if req not in collected_data or not collected_data[req]:
#                 missing.append(names[req])

#         if missing:
#             await call.message.answer(
#                 f"❌ <b>Не все показатели заполнены!</b>\n\n"
#                 f"Отсутствуют:\n" + "\n".join(missing)
#             )
#             await state.set_state(AdminState.collecting_data)
#             await edit_admin_message(
#                 bot,
#                 call.message.message_id,
#                 "📊 <b>Сбор показателей</b>\n\nВыберите показатель для ввода:",
#                 reply_markup=admin_main_keyboard()
#             )
#             return

#         count_users = await count_tenant_excel()

#         # Показываем прогресс
#         stages = [
#             (10, "🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Подготовка данных..."),
#             (20, "🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Сохранение показателей..."),
#             (30, "🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️⬛️", "Получение списка пользователей..."),
#             (40, "🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️", "Формирование отчетов..."),
#             (50, "🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️", "Создание Excel файлов..."),
#             (60, "🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️", "Отправка документов..."),
#             (70, "🟩🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️", "Отправка уведомлений..."),
#             (80, "🟩🟩🟩🟩🟩🟩🟩🟩⬛️⬛️", "Формирование отчета..."),
#             (90, "🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛️", "Завершение процесса..."),
#             (100, "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩", "✅ Готово!")
#         ]

#         # Шаг 1 - подготовка
#         await bot.edit_message_text(
#             chat_id=call.message.chat.id,
#             message_id=call.message.message_id,
#             text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                 f"{stages[0][1]} {stages[0][0]}%\n\n"
#                 f"{stages[0][2]}",
#             parse_mode=ParseMode.HTML
#         )
#         await asyncio.sleep(1)

#         print(f'Проверка перед отправкой в excel - {collected_data}')

#         # Шаг 2 - сохранение показателей
#         await bot.edit_message_text(
#             chat_id=call.message.chat.id,
#             message_id=call.message.message_id,
#             text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                 f"{stages[1][1]} {stages[1][0]}%\n\n"
#                 f"{stages[1][2]}",
#             parse_mode=ParseMode.HTML
#         )
#         await admin_indicators(collected_data)
#         await asyncio.sleep(0.5)

#         # Шаг 3 - получение списка пользователей
#         await bot.edit_message_text(
#             chat_id=call.message.chat.id,
#             message_id=call.message.message_id,
#             text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                 f"{stages[2][1]} {stages[2][0]}%\n\n"
#                 f"{stages[2][2]}",
#             parse_mode=ParseMode.HTML
#         )

#         all_users_record_list = await get_data('SELECT user_id FROM users')
#         list_users = []
#         for user in all_users_record_list:
#             list_users.append(user['user_id'])

#         await asyncio.sleep(0.5)

#         # Шаг 4-7 - обработка пользователей
#         total_users = len(list_users)
#         for idx, user in enumerate(list_users):
#             progress = 40 + int((idx / total_users) * 40) if total_users > 0 else 60
            
#             if progress < 50:
#                 indicator = "🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️⬛️"
#             elif progress < 60:
#                 indicator = "🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️⬛️"
#             elif progress < 70:
#                 indicator = "🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️"
#             elif progress < 80:
#                 indicator = "🟩🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️"
#             else:
#                 indicator = "🟩🟩🟩🟩🟩🟩🟩🟩⬛️⬛️"
            
#             await bot.edit_message_text(
#                 chat_id=call.message.chat.id,
#                 message_id=call.message.message_id,
#                 text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                     f"{indicator} {progress}%\n\n"
#                     f"Обработка пользователя {idx+1}/{total_users}...",
#                 parse_mode=ParseMode.HTML
#             )
            
#             text_for_user = await get_volume_and_amount_month(user)
#             file = await create_word(collected_data,user,count_users,info_list)
#             document = FSInputFile(file)
#             await call.message.answer_document(document=document, caption='Ваш счёт за оплату')
#             os.unlink(file)
#             # await bot.send_document(chat_id=int(user), document=document, caption='Ваш счёт на оплату за прошедший месяц')
#             await bot.send_message(chat_id=int(user), text=text_for_user)
            
#             await asyncio.sleep(0.3)

#         # Шаг 8 - формирование отчета
#         await bot.edit_message_text(
#             chat_id=call.message.chat.id,
#             message_id=call.message.message_id,
#             text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                 f"{stages[7][1]} {stages[7][0]}%\n\n"
#                 f"{stages[7][2]}",
#             parse_mode=ParseMode.HTML
#         )

#         success = True

#         if success:
#             # Шаг 9 - завершение
#             await bot.edit_message_text(
#                 chat_id=call.message.chat.id,
#                 message_id=call.message.message_id,
#                 text=f"🔄 <b>Сохранение данных...</b>\n\n"
#                     f"{stages[8][1]} {stages[8][0]}%\n\n"
#                     f"{stages[8][2]}",
#                 parse_mode=ParseMode.HTML
#             )
#             await asyncio.sleep(0.5)
            
#             report = "✅ Все показания успешно сохранены!\n\n"
            
#             names = {
#                 "electro": "⚡ Электроэнергия",
#                 "water_cold": "🚰 Холодная вода", 
#                 "expl": "🏢 Комм. услуги",
#                 "drainage": "💧 Водоотведение",
#                 "heating": "🔥 Отопление"
#             }
            
#             for reading_type, data in collected_data.items():
#                 label = names.get(reading_type, reading_type)
#                 report += f"{label}\n"
                
#                 if reading_type == 'heating':
#                     report += f"• Объем: {data.get('volume', 0)}\n"
#                     report += f"• Сумма: {data.get('amount', 0)} руб.\n\n"
#                 elif label == '🏢 Комм. услуги':
#                     report += f"• Сумма: {data['amount']} руб.\n\n"
#                 elif label == '💧 Водоотведение':
#                     report += f"• Ставка: {data['amount']} руб.\n\n"
#                 else:
#                     report += f"• Объем: {data['volume']}\n"
#                     report += f"• Сумма: {data['amount']} руб.\n\n"
            
#             report += f"📅 Время внесения: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
#             # Финальный шаг - 100%
#             await bot.edit_message_text(
#                 chat_id=call.message.chat.id,
#                 message_id=call.message.message_id,
#                 text=f"✅ <b>Сохранение завершено!</b>\n\n"
#                     f"{stages[9][1]} 100%\n\n"
#                     f"Данные успешно сохранены и отправлены {total_users} пользователям.",
#                 parse_mode=ParseMode.HTML
#             )
#             await asyncio.sleep(1)
            
#             await edit_admin_message(
#                 bot,
#                 call.message.message_id,
#                 report,
#                 reply_markup=admin_main_keyboard()
#             )
            
#             collected_data = {}
            
#         else:
#             await bot.edit_message_text(
#                 chat_id=call.message.chat.id,
#                 message_id=call.message.message_id,
#                 text=f"❌ <b>Ошибка при сохранении</b>\n\n"
#                     f"Не удалось записать данные в таблицу.",
#                 parse_mode=ParseMode.HTML
#             )
#             await asyncio.sleep(1)
            
#             await edit_admin_message(
#                 bot,
#                 call.message.message_id,
#                 "❌ Ошибка при сохранении\n\n"
#                 "Не удалось записать данные в таблицу.",
#                 reply_markup=admin_main_keyboard()
#             )
#     else:
#         # Обновляем клавиатуру - этот арендатор теперь должен быть "серым" или скрыт
#         keyboard = await tenants_keyboard(new_items,page=0)
        
#         await edit_admin_message(
#             bot,
#             call.message.message_id,
#             f"✅ Показания успешно сохранены!\n\n"
#             f"🔥 Отопление\n\n"
#             f"Выберите следующего арендатора:",
#             reply_markup=keyboard,
#             parse_mode="HTML"
#         )
#         await call.answer("Показания сохранены", show_alert=False)


# @admin_router.callback_query(F.data.startswith("edittenant_readings_"), StateFilter(AdminState.confirming_readings))
# async def edit_readings(call: CallbackQuery, state: FSMContext):
#     from main import bot
#     await state.set_state(AdminState.waiting_for_heat_volume)
    
#     data = await state.get_data()
#     tenant_name = data.get('selected_tenant_name', 'Арендатор')
#     print(f"EDIT CALLBACK RECEIVED: {call.data}")
#     print(tenant_name)
#     await call.message.edit_text(text=
#         f"✏️ Редактирование\n"
#         f"🔥 Отопление - {tenant_name}\n\n"
#         f"Введите новые показания счетчика:",
#         parse_mode="HTML"
#     )
#     await call.answer()


@admin_router.callback_query(F.data == "back_to_tenant_selection", StateFilter(AdminState.confirming_readings))
async def back_to_tenant_selection(call: CallbackQuery, state: FSMContext):
    from main import bot
    await state.set_state(AdminState.selecting_tenant)
    new_data = await state.get_data()
    new_items = new_data.get('list_tenant', [])
    keyboard = await tenants_keyboard(new_items,page=0)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        "🔥 Отопление\n\n"
        "Выберите арендатора:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await call.answer()
