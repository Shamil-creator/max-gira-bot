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

ALL_TYPES = ["electro", "water_cold", "drainage"]

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
        [InlineKeyboardButton(text="🔥 Отопление, Коммунальные услуги, Непредвиденные", callback_data="service_heat")],
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

_ADMIN_RENT_ACT_RE = re.compile(r'^Акт \d{2}\.\d{4}')


def admin_my_bills_sort_key(doc: Any) -> Tuple[int, float]:
    """Порядок для «Мои счета»: акт КУ → акт аренды → акт расчета → счёт аренды → счёт КУ → прочее."""
    fn = (doc.get('file_name') or '').strip()
    da = doc.get('date_added')
    if isinstance(da, datetime):
        ts = da.timestamp()
    elif isinstance(da, date):
        ts = datetime.combine(da, datetime.min.time()).timestamp()
    else:
        ts = 0.0

    if fn.startswith('Акт расчета КУ'):
        cat = 1
    elif fn.startswith('Акт КУ'):
        cat = 1
    elif fn.startswith('Акт №') and 'КУ' in fn:
        cat = 1
    elif _ADMIN_RENT_ACT_RE.match(fn):
        cat = 2
    elif fn.startswith('Акт расчета'):
        cat = 3
    elif fn.startswith('Счет на оплату аренды'):
        cat = 4
    elif fn.startswith('Счет на оплату КУ'):
        cat = 5
    else:
        cat = 6
    return (cat, -ts)


async def get_data(query: str, *params):
    """Основной метод работы с БД"""
    conn = None
    try:
        import asyncpg
        conn = await asyncpg.connect(config.db_connection)
        return await conn.fetch(query, *params)
    except Exception as e:
        logging.error(f"Ошибка БД: {e}")
        return None
    finally:
        if conn:
            await conn.close()

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


def validate_company_edit_field(param_key: str, new_value: str) -> Tuple[bool, str, Any]:
    """
    Валидация поля при редактировании компании.
    Возвращает (успех, текст_ошибки, значение_для_БД).
    """
    if param_key == "name_company":
        if len(new_value) > 50:
            return False, "Наименование не длиннее 50 символов (ограничение БД).", None
        return True, "", new_value
    if param_key == "square":
        try:
            v = float(new_value.replace(",", "."))
        except ValueError:
            return False, "Площадь должна быть числом (например 100 или 150.5).", None
        return True, "", v
    if param_key == "bid":
        try:
            v = float(new_value.replace(",", "."))
        except ValueError:
            return False, "Ставка должна быть числом.", None
        return True, "", v
    if param_key == "agreement":
        if len(new_value) > 50:
            return False, "Номер договора не длиннее 50 символов.", None
        return True, "", new_value
    if param_key == "contract_end_date":
        try:
            datetime.strptime(new_value, "%d.%m.%Y")
        except ValueError:
            return False, "Дата в формате ДД.ММ.ГГГГ (например 31.12.2025).", None
        return True, "", new_value
    if param_key == "acceptance_certificate":
        try:
            d = datetime.strptime(new_value, "%d.%m.%Y").date()
        except ValueError:
            return False, "Дата акта в формате ДД.ММ.ГГГГ.", None
        return True, "", d
    if param_key == "phone":
        return True, "", new_value
    if param_key == "director_name" or param_key == "director_fio_genitive":
        parts = new_value.split()
        if len(parts) < 3:
            return False, "Введите полное ФИО (минимум 3 слова).", None
        if not re.match(r"^[а-яА-ЯёЁ\s\-]+$", new_value):
            return False, "ФИО: только кириллица, пробелы и дефисы.", None
        return True, "", new_value
    if param_key == "activity_type":
        name = new_value.strip()
        if len(name) < 2:
            return False, "Слишком короткое название вида деятельности.", None
        return True, "", name
    return True, "", new_value


async def _admin_try_delete_user_message(bot: Bot, message: Message) -> None:
    """Удалить сообщение пользователя (работает и в личном чате, и в группе)."""
    try:
        await message.delete()
    except Exception as exc:
        logging.warning("Не удалось удалить сообщение %s в чате %s: %s", message.message_id, message.chat.id, exc)


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
    builder.button(text="📁 Мои счета", callback_data="admin_my_bills")
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
    builder.button(text='💧 Редактировать ставку водоотведения', callback_data='admin_edit_drainage')
    
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


@admin_router.message(Command("sendall"))
async def admin_sendall(message: Message, bot: Bot):
    """Рассылка всех автоматических документов и напоминаний каждому пользователю."""
    if not await has_admin_access(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        return

    admin_chat = message.chat.id
    await message.answer("📤 Рассылка всех автоматических документов и напоминаний...")

    from handlers.check_payment_status import (
        get_invoice_msg_every_month,
        get_act_of_payment,
        get_act_ku_payment_every_month,
        get_ku_invoice_every_month,
        get_message_every_month,
        get_mr_message_every_month,
        get_data as cps_get_data,
    )

    all_users = await cps_get_data("SELECT user_id FROM users")
    if not all_users:
        await bot.send_message(admin_chat, "Нет зарегистрированных пользователей.")
        return

    user_ids = [u["user_id"] for u in all_users]
    total = len(user_ids)
    ok_count = 0
    error_count = 0

    tasks = [
        ("Напоминание об оплате", get_message_every_month, False),
        ("Напоминание о показаниях", get_mr_message_every_month, False),
        ("Счёт на оплату аренды", get_invoice_msg_every_month, True),
        ("Акт аренды", get_act_of_payment, True),
        ("Счёт на оплату КУ", get_ku_invoice_every_month, True),
        ("Акт КУ", get_act_ku_payment_every_month, True),
    ]

    for idx, uid in enumerate(user_ids, 1):
        for label, func, has_force in tasks:
            try:
                if has_force:
                    await func(uid, force=True)
                else:
                    await func(uid)
                ok_count += 1
            except Exception as e:
                logging.exception("[sendall] %s для user %s: %s", label, uid, e)
                error_count += 1
        await asyncio.sleep(0.3)

    await bot.send_message(
        admin_chat,
        f"✅ /sendall завершён.\n"
        f"Пользователей: {total}\n"
        f"Отправлено: {ok_count}\n"
        f"Ошибок: {error_count}",
    )


# Храним собранные данные
collected_data = {}
unexpected_expenses = 0.0

@admin_router.callback_query(F.data == "admin_submit_readings_back", StateFilter(AdminState.choosing_method))
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
    elif kind == 'water_cold':  # Для холодной воды - только ставка
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
            f"Введите ставку для {label} (в рублях за м³):\n"
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
    """Обработка введенной ставки для холодной воды"""
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
            "Пожалуйста, введите корректную ставку (положительное число).",
            reply_markup=cancel_keyboard()
        )
        return
    
    data = await state.get_data()
    current_type = data.get("current_type")  # Должно быть "water_cold"
    
    # Сохраняем ставку
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
        f"• Ставка: {tariff} руб./м³\n\n"
        f"Собрано показаний: {sum(1 for t in ALL_TYPES if t in collected_data)} из {len(ALL_TYPES)}\n\n"
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
    
    report = f"✅ Данные сохранены\n\nСобрано показаний: {sum(1 for t in ALL_TYPES if t in collected_data)} из {len(ALL_TYPES)}\n\n"
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

        file = await create_word(collected_data, user, count_users, info_list, unexpected_expenses)
        document = FSInputFile(file)
        
        # Получаем индивидуальные суммы непредвиденных/эксплуатационных из БД
        user_business = await get_data(
            'SELECT id_business FROM users WHERE User_Id = $1', str(user)
        )
        user_unexp = 0
        user_expl = 0
        if user_business:
            bid = user_business[0]['id_business']
            # Читаем из Excel для этого пользователя (данные уже записаны add_tenant_for_user)
            try:
                from handlers.excel_tg_test import get_sheet_name_in_id_business
                import pandas as pd
                sheet = await get_sheet_name_in_id_business(bid)
                df = pd.read_excel('docs/ГИРА_1006теккаа2.xlsx', sheet_name=sheet, header=None).fillna(0)
                # Строка 12 = непредвиденные, строка 11 = эксплуатация (значение в последнем ненулевом столбце)
                for c in reversed(range(len(df.columns))):
                    try:
                        v = float(df.iloc[11, c])
                        if v > 0: user_unexp = v; break
                    except: continue
                for c in reversed(range(len(df.columns))):
                    try:
                        v = float(df.iloc[10, c])
                        if v > 0: user_expl = v; break
                    except: continue
            except:
                pass
        
        caption = '🧾 Ваш счёт за прошедший месяц'
        caption_parts = []
        if user_unexp > 0:
            caption_parts.append(f'💰 Непредвиденные расходы: {user_unexp:.2f} руб.')
        if user_expl > 0:
            caption_parts.append(f'🏢 Коммунальные услуги: {user_expl:.2f} руб.')
        if caption_parts:
            caption += '\n\n' + '\n'.join(caption_parts)
        
        await bot.send_document(
            chat_id=int(user),
            document=document,
            caption=caption
        )
        os.unlink(file)
        
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
            report += f"• Ставка: {data.get('tariff', 0)} руб./м³\n\n"
        elif reading_type == 'drainage':
            report += f"• Сумма: {data['amount']} руб.\n\n"
        elif reading_type == 'expl':
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
            f"Собрано показаний: {sum(1 for t in ALL_TYPES if t in collected_data)} из {len(ALL_TYPES)}\n\n"
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
            f"Собрано показаний: {sum(1 for t in ALL_TYPES if t in collected_data)} из {len(ALL_TYPES)}\n\n"
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
    if message.chat.id != ADMIN_CHAT_ID:
        return
    if not message.text:
        return

    raw_text = message.text.replace(",", ".")
    
    try:
        value = float(raw_text)
        if value < 0:
            raise ValueError
    except ValueError:
        await _admin_try_delete_user_message(bot, message)
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
        await _admin_try_delete_user_message(bot, message)
        await send_to_admin_topic(
            bot,
            "❌ Ошибка: не указан тип показаний",
            reply_markup=cancel_keyboard()
        )
        return
    
    # ОБНОВЛЕНИЕ: Проверка для эксплуатационных услуг
    if edit_type == "expl" and editing_field == "volume":
        await _admin_try_delete_user_message(bot, message)
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
    
    if edit_type == 'electro' and editing_field in ('volume', 'amount'):
        vol = collected_data[edit_type].get('volume', 0)
        amt = collected_data[edit_type].get('amount', 0)
        if vol and vol > 0:
            collected_data[edit_type]['tariff'] = round(float(amt) / float(vol), 6)
    
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
    
    message_text += f"• Сумма: {type_data.get('amount', '—')} руб.\n"
    
    if edit_type == 'electro' and 'tariff' in type_data:
        message_text += f"• Ставка: {round(type_data['tariff'], 4)} руб./кВт·ч\n"
    
    message_text += "\nЧто еще хотите изменить?"
    
    await send_to_admin_topic(
        bot,
        message_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await _admin_try_delete_user_message(bot, message)

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
        
        if current_type == 'electro':
            volume = collected_data[current_type].get('volume', 0)
            if volume > 0:
                collected_data[current_type]['tariff'] = round(amount / volume, 6)
        
        names = {
            "electro": "⚡ Электроэнергия",
            "water_cold": "🚰 Холодная вода", 
            "drainage": "💧 Водоотведение"
        }
        label = names.get(current_type, "")
        
        # Проверяем, все ли типы заполнены
        collected_types = list(collected_data.keys())
        
        missing_types = [t for t in ALL_TYPES if t not in collected_types]
        for type_miss in missing_types:
            if type_miss == 'electro':
                missing_types_for_users.append('электричество')
            elif type_miss == 'water_cold':
                missing_types_for_users.append('холодная вода')
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
        
        stavka_line = ""
        if current_type == 'electro' and 'tariff' in collected_data.get(current_type, {}):
            stavka_line = f"• Ставка: {round(collected_data[current_type]['tariff'], 4)} руб./кВт·ч\n"
        
        await send_to_admin_topic(
            bot,
            f"✅ Данные сохранены:\n\n"
            f"{label}\n"
            f"• Объем: {collected_data[current_type]['volume']} {unit_of_measurement}\n"
            f"• Сумма с НДС: {amount} руб.\n"
            f"{stavka_line}\n"
            f"Собрано показаний: {sum(1 for t in ALL_TYPES if t in collected_data)} из {len(ALL_TYPES)}\n\n"
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
                message_text += f"• Ставка: {data.get('tariff', 0)} руб./м³\n\n"
            if edit_type != "expl" or edit_type!= "drainage":
                message_text += f"• Объем: {type_data.get('volume', '—')}\n"
            
            message_text += f"• Сумма: {type_data.get('amount', '—')} руб.\n"
            
            if edit_type == 'electro' and 'tariff' in type_data:
                message_text += f"• Ставка: {round(type_data['tariff'], 4)} руб./кВт·ч\n"
            
            message_text += "\nЧто вы хотите изменить?"
            
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
                report += f"• Ставка: {data.get('tariff', 0)} руб./м³\n\n"
            elif reading_type == 'drainage':
                report += f"• Сумма: {data.get('amount', '—')} руб.\n\n"
            elif reading_type == 'electro':
                report += f"• Объем: {data.get('volume', '—')}\n"
                report += f"• Сумма: {data.get('amount', '—')} руб.\n"
                if 'tariff' in data:
                    report += f"• Ставка: {round(data['tariff'], 4)} руб./кВт·ч\n"
                report += "\n"
            else:
                report += f"• Объем: {data.get('volume', '—')}\n"
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
        # Для холодной воды - только ставка
        builder.button(text="💰 Редактировать ставку", callback_data=f"admin_edit_tariff_{edit_type}")
    elif edit_type == "drainage":
        # Водоотведение — только сумма (ставка)
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
        message_text += f"• Ставка: {type_data.get('tariff', '—')} руб./м³\n\n"
    elif edit_type == "drainage":
        message_text += f"• Сумма: {type_data.get('amount', '—')} руб.\n\n"
    elif edit_type == "electro":
        message_text += f"• Объем: {type_data.get('volume', '—')}\n"
        message_text += f"• Сумма: {type_data.get('amount', '—')} руб.\n"
        if 'tariff' in type_data:
            message_text += f"• Ставка: {round(type_data['tariff'], 4)} руб./кВт·ч\n"
        message_text += "\n"
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
    if edit_type == "drainage":
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
    
    if next_type == "drainage":
        await state.update_data(current_type=next_type, step="amount")
        await state.set_state(AdminState.waiting_for_amount_drainage)
        text = f"📊 Добавление следующего показателя\n\nВведите ставку для {get_type_names().get(next_type, '')}:"
    elif next_type == "water_cold":
        await state.update_data(current_type=next_type, step="tariff")
        await state.set_state(AdminState.waiting_for_tariff)
        text = f"📊 Добавление следующего показателя\n\nВведите ставку для {get_type_names().get(next_type, '')} (в рублях за м³):"
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
    
    # Проверяем, все ли арендаторы по отоплению обработаны (только те, у кого есть счётчики)
    query = """SELECT b.id FROM bussines b
               WHERE EXISTS (SELECT 1 FROM us_readings ur WHERE ur.business_id = b.id)
               ORDER BY b.name_company"""
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
    required_common = ["electro", "water_cold", "drainage"]
    missing_common = []
    common_names = {
        'electro': '⚡ Электроэнергия',
        'water_cold': '🚰 Холодная вода',
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
    
    # ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - можно предлагать файлы перед отправкой
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
        "drainage": "💧 Водоотведение"
    }
    
    for reading_type, data_item in collected_data.items():
        if reading_type == 'heating':
            continue
        label = names.get(reading_type, reading_type)
        report += f"{label}\n"
        
        if reading_type == "water_cold":
            report += f"• Ставка: {data_item.get('tariff', 0)} руб./м³\n\n"
        elif reading_type == "drainage":
            report += f"• Сумма: {data_item.get('amount', 0)} руб.\n\n"
        else:
            report += f"• Объем: {data_item.get('volume', 0)}\n"
            report += f"• Сумма: {data_item.get('amount', 0)} руб.\n\n"
    
    builder = InlineKeyboardBuilder()
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
    all_types = ["electro", "water_cold", "water_hot", "drainage", "heating"]
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
                report += f"• Ставка: {data_item.get('tariff', 0)} руб./м³\n\n"
            elif reading_type == "drainage":
                report += f"• Сумма: {data_item.get('amount', 0)} руб.\n\n"
            elif reading_type == "expl":
                report += f"• Сумма: {data_item.get('amount', 0)} руб.\n\n"
            else:
                report += f"• Объем: {data_item.get('volume', 0)}\n"
                report += f"• Сумма: {data_item.get('amount', 0)} руб.\n\n"
        
        builder = InlineKeyboardBuilder()
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
    try:
        await admin_indicators(collected_data)
    except Exception as e:
        logging.exception("admin_indicators: не удалось сохранить показатели в Excel: %s", e)
        try:
            await bot.send_message(
                chat_id=call.message.chat.id,
                text=f"⚠️ <b>Показатели в общий Excel не записаны.</b>\nПричина: <code>{e}</code>\nРассылка продолжается...",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
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
        
        # Проверяем наличие счётчиков у арендатора
        from handlers.run import get_info_business, get_form_of_doing_info_business
        from handlers.meter_readings import get_sheet_name
        records = await get_data('SELECT id_business FROM users WHERE User_Id = $1', str(user))
        id_business = None
        if records and records[0]['id_business']:
            id_business = records[0]['id_business']

        has_meters = False
        if id_business is not None:
            try:
                meters_check = await get_data(
                    'SELECT COUNT(*) as cnt FROM us_readings WHERE business_id = $1',
                    id_business
                )
                has_meters = meters_check and meters_check[0]['cnt'] > 0
            except Exception:
                has_meters = False

        print(f"[DEBUG] Пользователь {user}: id_business={id_business}, has_meters={has_meters}")

        if not has_meters:
            print(f"[DEBUG] Пользователь {user}: нет счётчиков — пропускаем Акт и Счёт КУ")
            continue

        # Создаем и отправляем Акт + Счёт КУ
        print(f"{collected_data}")
        print(f"Пользователь {user}")
        print(f"{count_users}")
        print(f"{info_list}")
        print(f"{unexpected_expenses}")
        word_result = await create_word(user, count_users, collected_data, info_list, unexpected_expenses, get_info_business, get_sheet_name)
        if isinstance(word_result, tuple):
            file, ku_total = word_result
        else:
            file, ku_total = word_result, 0
        
        print(f"[DEBUG] Пользователь {user}: file={'OK' if file else 'None'}, ku_total={ku_total}")
        
        if file is None:
            await bot.send_message(
                chat_id=call.message.chat.id,
                text=f"⚠️ <b>Ошибка генерации документа!</b>\n"
                     f"Не удалось создать файл для пользователя <code>{user}</code> (скорее всего, в Excel нет показаний дат за прошлый/текущий месяц). Выставляем счёт следующему арендатору...",
                parse_mode="HTML"
            )
            continue
            
        # Генерируем красивое имя файла на основе периода и формы бизнеса
        fod_name = await get_form_of_doing_info_business(user)
        nice_filename = f"Акт расчета КУ {fod_name} {period_str}.docx"
        document = FSInputFile(file, filename=nice_filename)
        
        # Индивидуальные суммы для caption
        user_unexp_final = 0
        user_expl_final = 0
        try:
            from handlers.excel_tg_test import get_sheet_name_in_id_business
            import pandas as pd
            sheet = await get_sheet_name_in_id_business(id_business)
            df = pd.read_excel('docs/ГИРА_1006теккаа2.xlsx', sheet_name=sheet, header=None).fillna(0)
            for c in reversed(range(len(df.columns))):
                try:
                    v = float(df.iloc[11, c])
                    if v > 0: user_unexp_final = v; break
                except: continue
            for c in reversed(range(len(df.columns))):
                try:
                    v = float(df.iloc[10, c])
                    if v > 0: user_expl_final = v; break
                except: continue
        except:
            pass
        
        caption = '🧾 Ваш счёт за прошедший месяц'
        caption_parts = []
        if user_unexp_final > 0:
            caption_parts.append(f'💰 Непредвиденные расходы: {user_unexp_final:.2f} руб.')
        if user_expl_final > 0:
            caption_parts.append(f'🏢 Коммунальные услуги: {user_expl_final:.2f} руб.')
        if caption_parts:
            caption += '\n\n' + '\n'.join(caption_parts)
        
        try:
            sent_message = await bot.send_document(
                chat_id=int(user),
                document=document,
                caption=caption
            )
        except Exception as e:
            logging.exception("Не удалось отправить счёт пользователю %s: %s", user, e)
            try:
                await bot.send_message(
                    chat_id=call.message.chat.id,
                    text=f"⚠️ Не удалось отправить счёт пользователю <code>{user}</code>: <code>{e}</code>\nСледующий арендатор...",
                    parse_mode="HTML",
                )
            except Exception:
                pass
            try:
                os.unlink(file)
            except OSError:
                pass
            continue

        today_date = date.today()
        file_id = sent_message.document.file_id
        if not id_business:
            logging.warning(f"Пользователь {user} не найден в таблице Users или не привязан к бизнесу. Пропускаем запись документа.")
        else:
            try:
                await new_data_insert('INSERT INTO business_documents(id_business, file_id, date_added, file_name) VALUES ($1, $2, $3, $4)', id_business, file_id, today_date, nice_filename)
            except Exception as e:
                logging.exception("Не удалось записать business_documents для пользователя %s: %s", user, e)

        # Дублируем файл в админский чат
        try:
            await bot.send_document(
                chat_id=call.message.chat.id,
                document=FSInputFile(file, filename=nice_filename),
                caption=f"📁 Копия счёта ({nice_filename}), отправленного арендатору: <code>{user}</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.exception("Не удалось отправить копию счёта в админский чат для пользователя %s: %s", user, e)

        try:
            os.unlink(file)
        except OSError as e:
            logging.warning("Не удалось удалить временный файл %s: %s", file, e)

        # Генерация и отправка Счёта КУ (xlsx)
        try:
            from handlers.create_layout import create_invoice_for_ku_for_user
            biz_records = await get_info_business(user)
            fod_name = await get_form_of_doing_info_business(user)
            if biz_records:
                biz = biz_records[0]
                ku_full_name = f'''{fod_name} "{biz['name_company']}"'''
                ku_agreement = biz.get('agreement', '')
                ku_number = int(biz.get('number_act_ku') or 0) + 1
                ku_full_name_tenant = f"{biz['surname']} {biz['first_name']} {biz['patronymic']}"

                ku_xlsx_path = await create_invoice_for_ku_for_user(
                    act_number=ku_number,
                    name_company='ООО "ГИРА"',
                    name_company_tenant=ku_full_name,
                    agreement=ku_agreement,
                    price=ku_total,
                    square=biz.get('square', 0),
                    start_period=start,
                    end_period=end,
                    full_name_tenant=ku_full_name_tenant,
                    tenant_director_title=biz.get('director_title') or 'Директор',
                )
                ku_nice_filename = f"Счет на оплату КУ {period_str}.xlsx"
                ku_document = FSInputFile(ku_xlsx_path, filename=ku_nice_filename)

                ku_sent = await bot.send_document(
                    chat_id=int(user),
                    document=ku_document,
                    caption='📄 Ваш счёт на оплату КУ за прошедший месяц'
                )

                await new_data_insert(
                    'UPDATE bussines SET number_act_ku = $1 WHERE id = $2',
                    ku_number, id_business
                )
                ku_file_id = ku_sent.document.file_id
                await new_data_insert(
                    'INSERT INTO business_documents(id_business, file_id, date_added, file_name) VALUES ($1, $2, $3, $4)',
                    id_business, ku_file_id, today_date, ku_nice_filename
                )

                await bot.send_document(
                    chat_id=call.message.chat.id,
                    document=FSInputFile(ku_xlsx_path, filename=ku_nice_filename),
                    caption=f"📁 Копия счёта КУ ({ku_nice_filename}), отправленного арендатору: <code>{user}</code>",
                    parse_mode="HTML"
                )

                try:
                    os.unlink(ku_xlsx_path)
                except OSError:
                    pass
        except Exception as e:
            logging.exception("Не удалось сгенерировать/отправить счёт КУ пользователю %s: %s", user, e)

        # Отправляем приложенные документы
        for doc in documents:
            try:
                mime = (doc.get('mime_type') or "").lower()
                attach_file_id = doc.get('file_id')
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
                            photo=attach_file_id,
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
                            video=attach_file_id,
                            caption=f"🎬 Подтверждающее видео"
                        )
                else:
                    # Это документ - отправляем как документ (токен для файлов работает)
                    await bot.send_document(
                        chat_id=int(user),
                        document=attach_file_id,
                        caption=f"📎 Подтверждающий документ: {file_name}"
                    )
            except Exception as e:
                logging.exception("Не удалось отправить вложение пользователю %s (%s): %s", user, doc.get('file_name'), e)

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
            report += f"• Ставка: {data.get('tariff', 0)} руб./м³\n\n"
        elif reading_type == "drainage":
            report += f"• Сумма: {data.get('amount', 0)} руб.\n\n"
        elif reading_type == "expl":
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

@admin_router.callback_query(F.data == "admin_my_bills")
async def admin_my_bills(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Мои счета — список компаний для просмотра документов"""
    companies = await get_data(
        'SELECT b.id, b.name_company FROM bussines b ORDER BY b.name_company'
    )
    if not companies:
        await call.answer("Нет компаний")
        return
    
    builder = InlineKeyboardBuilder()
    for comp in companies:
        builder.row(InlineKeyboardButton(
            text=f"📁 {comp['name_company'] or 'ID: ' + str(comp['id'])}",
            callback_data=f"admin_bills_{comp['id']}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_to_main"))
    builder.adjust(1)
    
    await state.set_state(AdminState.viewing_bills)
    await edit_admin_message(
        bot,
        call.message.message_id,
        "📁 <b>Мои счета</b>\n\nВыберите компанию для просмотра документов:",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML,
    )
    await call.answer()

@admin_router.callback_query(F.data.startswith("admin_bills_"), StateFilter(AdminState.viewing_bills))
async def admin_view_company_bills(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Показать документы выбранной компании"""
    company_id = int(call.data.split("_")[2])
    
    company = await get_data('SELECT name_company FROM bussines WHERE id = $1', company_id)
    company_name = company[0]['name_company'] if company else 'Компания'
    
    docs = await get_data(
        'SELECT file_id, file_name, date_added FROM business_documents '
        'WHERE id_business = $1',
        company_id,
    )
    if docs:
        docs = sorted(docs, key=admin_my_bills_sort_key)
    
    if not docs:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_my_bills"))
        await edit_admin_message(
            bot,
            call.message.message_id,
            f"📁 <b>{company_name}</b>\n\nДокументов пока нет.",
            reply_markup=builder.as_markup(),
            parse_mode=ParseMode.HTML,
        )
        await call.answer()
        return
    
    total = len(docs)
    await call.message.edit_text(
        f"📁 <b>{company_name}</b>\n\n"
        f"К отправке файлов: <b>{total}</b>\n\n"
        "Документы 👇",
        parse_mode=ParseMode.HTML,
    )
    
    sent_ok = 0
    for doc in docs:
        try:
            fname = doc.get('file_name') or "Документ"
            await bot.send_document(
                chat_id=call.message.chat.id,
                document=doc['file_id'],
                caption=f"📄 {fname}",
                filename=fname
            )
            sent_ok += 1
        except Exception:
            await bot.send_message(call.message.chat.id, f"⚠️ Не удалось отправить: {fname}")
    
    await state.set_state(AdminState.admin_menu)
    if sent_ok == total:
        tail = f"Отправлено файлов: <b>{sent_ok}</b>."
    else:
        tail = f"Удалось отправить: <b>{sent_ok}</b> из <b>{total}</b>."
    await bot.send_message(
        call.message.chat.id,
        "📎 <b>Все документы по этой компании отправлены выше.</b>\n\n"
        f"{tail}\n\n"
        "На этом список документов закончился. Другую компанию можно открыть "
        "через «Мои счета», либо выберите любое действие в админ-панели:",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_main_keyboard(),
    )
    await call.answer()

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
            
            names = get_type_labels()
            
            for reading_type in ALL_TYPES:
                label = names.get(reading_type, reading_type)
                if reading_type in collected_data:
                    data = collected_data[reading_type]
                    report += f"✅ {label}\n"
                    if reading_type == 'water_cold':
                        report += f"• Ставка: {data.get('tariff', '—')} руб./м³\n\n"
                    elif reading_type == 'drainage':
                        report += f"• Сумма: {data.get('amount', '—')} руб.\n\n"
                    else:
                        report += f"• Объем: {data.get('volume', '—')}\n"
                        report += f"• Сумма: {data.get('amount', '—')} руб.\n\n"
                else:
                    report += f"❌ {label} — не заполнено\n\n"
            
            builder = InlineKeyboardBuilder()
            
            # Проверяем, все ли типы заполнены
            collected_types = list(collected_data.keys())
            missing_types = [t for t in ALL_TYPES if t not in collected_types]
            
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
        query = "SELECT user_id FROM users WHERE user_id != $1"
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

USERS_PER_PAGE = 8


async def _build_user_list_keyboard(page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    query = """
    SELECT u.user_id, u.username, u.first_name, u.second_name,
           b.name_company
    FROM users u
    LEFT JOIN bussines b ON b.id = u.id_business
    ORDER BY b.name_company NULLS LAST, u.user_id
    """
    users = await get_data(query) or []
    total = len(users)

    if total == 0:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_list"))
        return "👥 <b>Пользователи</b>\n\nНет зарегистрированных пользователей.", builder.as_markup()

    start = page * USERS_PER_PAGE
    end = start + USERS_PER_PAGE
    page_users = users[start:end]
    total_pages = (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE

    builder = InlineKeyboardBuilder()
    for u in page_users:
        uid = u["user_id"]
        company = u.get("name_company") or "без компании"
        uname = u.get("username") or ""
        label = f"{company}"
        if uname:
            label += f" (@{uname})"
        if len(label) > 40:
            label = label[:38] + "…"
        builder.row(InlineKeyboardButton(text=label, callback_data=f"admusr:{uid}"))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"usrpage_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if end < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"usrpage_{page + 1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_list"))

    text = f"👥 <b>Пользователи</b> ({total})\n\nВыберите для редактирования:"
    return text, builder.as_markup()


async def _build_user_detail(user_id: str) -> Optional[Tuple[str, InlineKeyboardMarkup]]:
    query = """
    SELECT u.user_id, u.username, u.first_name, u.second_name, u.patronymic,
           u.phone_number, b.name_company, u.id_business
    FROM users u
    LEFT JOIN bussines b ON b.id = u.id_business
    WHERE u.user_id = $1
    """
    rows = await get_data(query, user_id)
    if not rows:
        return None
    u = dict(rows[0])
    fio_parts = [
        str(u.get("second_name") or "").strip(),
        str(u.get("first_name") or "").strip(),
        str(u.get("patronymic") or "").strip(),
    ]
    fio = " ".join(p for p in fio_parts if p) or "не указано"
    uname = u.get("username") or "не указан"
    phone = str(u.get("phone_number") or "").strip() or "не указан"
    company = u.get("name_company") or "не привязан"

    lines = [
        "👤 <b>Карточка пользователя</b>\n",
        f"🆔 <b>Telegram ID:</b> <code>{u['user_id']}</code>",
        f"📱 <b>Username:</b> @{uname}" if uname != "не указан" else f"📱 <b>Username:</b> {uname}",
        f"👤 <b>ФИО:</b> {fio}",
        f"📞 <b>Телефон:</b> {phone}",
        f"🏢 <b>Компания:</b> {company}",
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 ФИО", callback_data=f"edtusr_fio:{user_id}"),
            InlineKeyboardButton(text="📞 Телефон", callback_data=f"edtusr_phone:{user_id}"),
        ],
        [InlineKeyboardButton(text="🏢 Сменить компанию", callback_data=f"edtusr_company:{user_id}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="admin_users_hub")],
    ])
    return "\n".join(lines), kb


@admin_router.callback_query(F.data == "admin_users_hub")
async def admin_users_hub(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.managing_users)
    text, kb = await _build_user_list_keyboard(0)
    await callback.message.edit_text(text=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("usrpage_"), StateFilter(AdminState.managing_users))
async def users_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[1])
    text, kb = await _build_user_list_keyboard(page)
    await callback.message.edit_text(text=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admusr:"), StateFilter(AdminState.managing_users))
async def admin_user_selected(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split(":")[1]
    view = await _build_user_detail(user_id)
    if not view:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    text, kb = view
    await callback.message.edit_text(text=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(AdminState.user_detail)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("edtusr_fio:"), StateFilter(AdminState.user_detail))
async def edit_user_fio_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split(":")[1]
    await state.update_data(edit_user_id=user_id, edit_user_param="fio")
    await state.set_state(AdminState.edit_user_param)
    from main import bot
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="✏️ Введите <b>ФИО</b> (Фамилия Имя Отчество):",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("edtusr_phone:"), StateFilter(AdminState.user_detail))
async def edit_user_phone_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split(":")[1]
    await state.update_data(edit_user_id=user_id, edit_user_param="phone")
    await state.set_state(AdminState.edit_user_param)
    from main import bot
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="✏️ Введите <b>номер телефона</b>:",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("edtusr_company:"), StateFilter(AdminState.user_detail))
async def edit_user_company_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split(":")[1]
    companies = await get_companies_from_db()
    if not companies:
        await callback.answer("Нет компаний для привязки", show_alert=True)
        return
    rows = [
        [InlineKeyboardButton(text=c["name"], callback_data=f"reassign_{user_id}_{c['id']}")]
        for c in companies
    ]
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"admusr:{user_id}")])
    await state.set_state(AdminState.selecting_user_company)
    await state.update_data(edit_user_id=user_id)
    await callback.message.edit_text(
        "🏢 Выберите компанию для привязки пользователя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@admin_router.callback_query(
    F.data.startswith("reassign_"),
    StateFilter(AdminState.selecting_user_company),
)
async def reassign_user_company(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Ошибка формата", show_alert=True)
        return
    user_id = parts[1]
    company_id = int(parts[2])

    sheet_rows = await get_data("SELECT sheet_name FROM bussines WHERE id = $1", company_id)
    sheet_name = sheet_rows[0]["sheet_name"] if sheet_rows and sheet_rows[0]["sheet_name"] else None

    if sheet_name:
        await new_data_insert(
            "UPDATE users SET id_business = $1, sheets_name = $2 WHERE user_id = $3",
            company_id, sheet_name, user_id,
        )
    else:
        await new_data_insert(
            "UPDATE users SET id_business = $1 WHERE user_id = $2",
            company_id, user_id,
        )

    view = await _build_user_detail(user_id)
    if not view:
        await callback.answer("Ошибка", show_alert=True)
        return
    text, kb = view
    await callback.message.edit_text(
        text=f"✅ Компания обновлена!\n\n{text}",
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(AdminState.user_detail)
    await callback.answer()


@admin_router.message(StateFilter(AdminState.edit_user_param))
async def process_edit_user_value(message: Message, state: FSMContext, bot: Bot):
    if not message.text:
        return
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    param = data.get("edit_user_param")
    if not user_id or not param:
        await message.answer("Ошибка данных.")
        await state.clear()
        return

    new_value = message.text.strip()

    if param == "fio":
        parts = new_value.split()
        if len(parts) < 3:
            await message.answer("❌ Введите полное ФИО (минимум 3 слова).\nПопробуйте снова.")
            return
        if not re.match(r"^[а-яА-ЯёЁ\s\-]+$", new_value):
            await message.answer("❌ ФИО: только кириллица, пробелы и дефисы.\nПопробуйте снова.")
            return
        surname = parts[0]
        first_name = parts[1]
        patronymic = " ".join(parts[2:])
        await new_data_insert(
            "UPDATE users SET second_name=$1, first_name=$2, patronymic=$3 WHERE user_id=$4",
            surname, first_name, patronymic, user_id,
        )
    elif param == "phone":
        cleaned = re.sub(r"[\s\-\(\)]", "", new_value)
        if len(cleaned) < 6 or len(cleaned) > 15:
            await message.answer("❌ Некорректный номер телефона.\nПопробуйте снова.")
            return
        await new_data_insert(
            "UPDATE users SET phone_number=$1 WHERE user_id=$2",
            cleaned[:10], user_id,
        )
    else:
        await message.answer("Неизвестный параметр.")
        return

    view = await _build_user_detail(user_id)
    if not view:
        await message.answer("Ошибка загрузки данных.")
        return
    text, kb = view
    await state.set_state(AdminState.user_detail)
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Обновлено!\n\n{text}",
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )







async def get_companies_from_db() -> List[Dict]:
    try:
        query = "SELECT id, name_company FROM bussines ORDER BY name_company"
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
        FROM bussines b
        LEFT JOIN form_of_doing_business fdb ON b.id_form = fdb.id
        LEFT JOIN type_of_activity toa ON b.id_type_of_activity = toa.id
        WHERE b.id = $1
        """
        records_list = await get_data(query, company_id)
        
        if records_list and len(records_list) > 0:
            row = dict(records_list[0])
            # contract_end_date — псевдоним для end_date_agreement
            end_date = row.get("end_date_agreement")
            if end_date:
                row["contract_end_date"] = str(end_date).strip()
            # acceptance_certificate — date → ДД.ММ.ГГГГ
            acc_cert = row.get("acceptance_certificate")
            if acc_cert and hasattr(acc_cert, "strftime"):
                row["acceptance_certificate"] = acc_cert.strftime("%d.%m.%Y")
            # Телефон хранится в bussines.phone
            phone_val = str(row.get("phone") or "").strip()
            if phone_val:
                row["phone"] = phone_val
            else:
                row.pop("phone", None)
            # ФИО хранится тремя колонками: surname, first_name, patronymic
            parts = [
                str(row.get("surname") or "").strip(),
                str(row.get("first_name") or "").strip(),
                str(row.get("patronymic") or "").strip(),
            ]
            full_name = " ".join(p for p in parts if p)
            if full_name:
                row["director_name"] = full_name
            else:
                row.pop("director_name", None)
            return row
        return {}
    except Exception as e:
        print(f"Ошибка при получении деталей компании: {e}")
        return {}


async def build_company_detail_view(company_id: int) -> Optional[Tuple[str, InlineKeyboardMarkup]]:
    """Текст и клавиатура карточки компании (как в company_selected)."""
    company_details = await get_company_details(company_id)
    if not company_details:
        return None
    meters_records = await get_data(
        "SELECT ur.number_counter, tc.name FROM us_readings ur "
        "JOIN type_counter tc ON ur.counter_type_id = tc.id "
        "WHERE ur.business_id = $1 ORDER BY tc.id",
        company_id,
    )
    meters_lines = []
    if meters_records:
        for m in meters_records:
            t = m["name"]
            n = m["number_counter"]
            if t == "Холодная вода":
                meters_lines.append(f"  ❄️ ХВС: {n}")
            elif t == "Горячая вода":
                meters_lines.append(f"  🔥 ГВС: {n}")
            elif t == "Электричество":
                meters_lines.append(f"  ⚡ Электричество: {n}")
    meters_text = "\n".join(meters_lines) if meters_lines else "  нет счетчиков"
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
        f"👤 <b>ФИО:</b> {company_details.get('director_name', 'не указан')}",
    ]
    director_title_val = company_details.get('director_title')
    if director_title_val:
        info_lines.append(f"👔 <b>Должность:</b> {director_title_val}")
    director_fio_genitive_val = company_details.get('director_fio_genitive')
    if director_fio_genitive_val:
        info_lines.append(f"👤 <b>ФИО в Р.П.:</b> {director_fio_genitive_val}")
    info_lines.extend([
        f"🏢 <b>Вид деятельности:</b> {company_details.get('activity_name', 'не указан')}",
        f"\n📊 <b>Счетчики:</b>\n{meters_text}",
    ])
    text = "\n".join(info_lines)
    keyboard = await create_company_actions_keyboard(company_id)
    return text, keyboard


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
        query = "SELECT id, name FROM type_of_activity ORDER BY name"
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
        [InlineKeyboardButton(text="📊 Счетчики", callback_data=f"comp_meters_{company_id}")],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="back_to_list")]
    ])

async def create_edit_choice_keyboard(company_id: int, id_form: int = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Наименование", callback_data=f"edit_name:{company_id}"),
            InlineKeyboardButton(text="Площадь", callback_data=f"edit_square:{company_id}")
        ],
        [
            InlineKeyboardButton(text="Ставка", callback_data=f"edit_bid:{company_id}"),
            InlineKeyboardButton(text="Акт п/п", callback_data=f"edit_acceptance:{company_id}")
        ],
        [
            InlineKeyboardButton(text="Договор", callback_data=f"edit_agreement:{company_id}"),
            InlineKeyboardButton(text="Дата заверш.", callback_data=f"edit_contract_end:{company_id}")
        ],
        [
            InlineKeyboardButton(text="📞 Телефон", callback_data=f"edit_phone:{company_id}"),
            InlineKeyboardButton(text="👤 ФИО", callback_data=f"edit_director:{company_id}")
        ],
        [
            InlineKeyboardButton(text="📋 Форма бизнеса", callback_data=f"edit_form:{company_id}"),
            InlineKeyboardButton(text="🏢 Вид деятельности", callback_data=f"edit_activity:{company_id}")
        ],
    ]
    if id_form == 1:
        rows.append([
            InlineKeyboardButton(text="👔 Должность руководителя", callback_data=f"edit_director_title:{company_id}")
        ])
        rows.append([
            InlineKeyboardButton(text="👤 ФИО в Р.П.", callback_data=f"edit_genitive:{company_id}")
        ])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"company:{company_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

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

@admin_router.callback_query(
    F.data.startswith("company:"),
    StateFilter(
        AdminState.company_list,
        AdminState.company_action,
        AdminState.edit_param,
        AdminState.editing_meters,
        AdminState.adding_meter_number,
        AdminState.editing_meter_number,
    ),
)
async def company_selected(callback: CallbackQuery, state: FSMContext):
    company_id = int(callback.data.split(":")[1])
    view = await build_company_detail_view(company_id)
    if not view:
        await callback.answer("Компания не найдена!")
        return
    text, keyboard = view
    await callback.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.company_action)
    await callback.answer()

@admin_router.callback_query(
    F.data.startswith("editcomp_"),
    StateFilter(AdminState.company_action, AdminState.edit_param),
)
async def edit_company(callback: CallbackQuery, state: FSMContext):
    company_id = int(callback.data.split("_")[1])
    
    company_details = await get_company_details(company_id)
    if not company_details:
        await callback.answer("Компания не найдена!")
        return
    
    keyboard = await create_edit_choice_keyboard(company_id, id_form=company_details.get('id_form'))
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование компании</b>\n\n"
        f"Выберите параметр для редактирования <b>{company_details.get('name_company', 'Компания')}</b>:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.edit_param)
    await callback.answer()

@admin_router.callback_query(F.data.startswith("edit_form:"), StateFilter(AdminState.edit_param))
async def edit_company_form_menu(callback: CallbackQuery, state: FSMContext):
    company_id = int(callback.data.split(":")[1])
    forms = await get_business_forms()
    if not forms:
        await callback.answer("Нет форм в справочнике", show_alert=True)
        return
    rows = [
        [InlineKeyboardButton(text=form["name"], callback_data=f"bizf_{company_id}_{form['id']}")]
        for form in forms
    ]
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"editcomp_{company_id}")])
    await callback.message.edit_text(
        "Выберите <b>форму бизнеса</b>:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()

@admin_router.callback_query(F.data.startswith("bizf_"), StateFilter(AdminState.edit_param))
async def edit_company_form_pick(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Ошибка формата", show_alert=True)
        return
    company_id = int(parts[1])
    form_id = int(parts[2])
    await new_data_insert(
        "UPDATE bussines SET id_form = $1 WHERE id = $2",
        form_id,
        company_id,
    )
    view = await build_company_detail_view(company_id)
    if not view:
        await callback.answer("Компания не найдена", show_alert=True)
        return
    text, keyboard = view
    await callback.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(AdminState.company_action)
    await callback.answer("Форма обновлена")

@admin_router.callback_query(F.data.startswith("edit_director_title:"), StateFilter(AdminState.edit_param))
async def edit_director_title_menu(callback: CallbackQuery, state: FSMContext):
    company_id = int(callback.data.split(":")[1])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Генеральный директор", callback_data=f"dt_{company_id}_gen")],
        [InlineKeyboardButton(text="Директор", callback_data=f"dt_{company_id}_dir")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"editcomp_{company_id}")],
    ])
    await callback.message.edit_text(
        "Выберите <b>должность руководителя</b>:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()

@admin_router.callback_query(F.data.startswith("dt_"), StateFilter(AdminState.edit_param))
async def edit_director_title_pick(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Ошибка формата", show_alert=True)
        return
    company_id = int(parts[1])
    title_key = parts[2]
    title = "Генеральный директор" if title_key == "gen" else "Директор"
    await new_data_insert(
        "UPDATE bussines SET director_title = $1 WHERE id = $2",
        title,
        company_id,
    )
    view = await build_company_detail_view(company_id)
    if not view:
        await callback.answer("Компания не найдена", show_alert=True)
        return
    text, keyboard = view
    await callback.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(AdminState.company_action)
    await callback.answer("Должность обновлена")

@admin_router.callback_query(F.data.startswith("edit_"), StateFilter(AdminState.edit_param))
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
        "edit_director": ("ФИО", "director_name"),
        "edit_activity": ("вид деятельности", "activity_type"),
        "edit_genitive": ("ФИО в Р.П.", "director_fio_genitive"),
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
    )
    
    from main import bot
    
    if param_key == "director_fio_genitive":
        hint_text = " ('в лице кого?')\n<i>Пример: Иванова Ивана Ивановича</i>\n\n"
    else:
        hint_text = "\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"editcomp_{company_id}")]
    ])

    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=f"✏️ Введите новое значение для <b>{param_name}</b>{hint_text}"
             f"Текущее значение: <code>{current_value}</code>\n\n"
             f"<i>Отправьте новое значение в ответе:</i>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@admin_router.message(AdminState.edit_param)
async def process_edit_value(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    company_id = data.get("edit_company_id")
    param_key = data.get("edit_param_key")
    param_name = data.get("edit_param_name")
    
    if not all([company_id, param_key]):
        await message.answer("Ошибка данных! Попробуйте снова.")
        await state.clear()
        return

    if not message.text:
        return

    new_value = message.text.strip()

    ok, err_msg, db_val = validate_company_edit_field(param_key, new_value)
    if not ok:
        await message.answer(f"❌ {err_msg}\nПопробуйте снова.")
        return

    db_column_map = {
        'name_company': 'name_company',
        'square': 'square',
        'bid': 'bid',
        'agreement': 'agreement',
        'contract_end_date': 'end_date_agreement',
        'acceptance_certificate': 'acceptance_certificate',
        'phone': None,
        'director_name': None,
        'activity_type': None,
        'director_fio_genitive': 'director_fio_genitive',
    }
    db_column = db_column_map.get(param_key)
    if param_key == 'director_name':
        parts = new_value.split()
        surname = parts[0] if len(parts) > 0 else ''
        firstname = parts[1] if len(parts) > 1 else ''
        patronymic = ' '.join(parts[2:]) if len(parts) > 2 else ''
        await new_data_insert(
            'UPDATE bussines SET surname=$1, first_name=$2, patronymic=$3 WHERE id=$4',
            surname, firstname, patronymic, company_id
        )
    elif param_key == 'phone':
        await new_data_insert(
            'UPDATE bussines SET phone=$1 WHERE id=$2',
            new_value, company_id
        )
    elif param_key == 'activity_type':
        await new_data_insert(
            'INSERT INTO type_of_activity (name) VALUES ($1) ON CONFLICT (name) DO NOTHING',
            db_val,
        )
        rows = await get_data(
            'SELECT id FROM type_of_activity WHERE name = $1 LIMIT 1',
            db_val,
        )
        if not rows:
            await message.answer("❌ Не удалось сохранить вид деятельности. Попробуйте снова.")
            return
        id_toa = rows[0]['id']
        await new_data_insert(
            'UPDATE bussines SET id_type_of_activity = $1 WHERE id = $2',
            id_toa,
            company_id,
        )
    elif db_column:
        await new_data_insert(
            f'UPDATE bussines SET {db_column} = $1 WHERE id = $2',
            db_val,
            company_id,
        )

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
        f"👤 <b>ФИО:</b> {company_details.get('director_name', 'не указан')}"
    ]
    director_title_val2 = company_details.get('director_title')
    if director_title_val2:
        info_lines.append(f"👔 <b>Должность:</b> {director_title_val2}")
    director_fio_genitive_val2 = company_details.get('director_fio_genitive')
    if director_fio_genitive_val2:
        info_lines.append(f"👤 <b>ФИО в Р.П.:</b> {director_fio_genitive_val2}")
    
    keyboard = await create_company_actions_keyboard(company_id)

    await bot.send_message(
        chat_id=message.chat.id,
        text="\n".join(info_lines),
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

@admin_router.callback_query(F.data.startswith("comp_meters_"))
async def view_company_meters(callback: CallbackQuery, state: FSMContext):
    """Просмотр и управление счетчиками компании"""
    company_id = int(callback.data.split("_")[2])
    await state.update_data(meters_company_id=company_id)
    await state.set_state(AdminState.editing_meters)
    
    meters_records = await get_data(
        'SELECT ur.id, ur.number_counter, tc.name FROM us_readings ur '
        'JOIN type_counter tc ON ur.counter_type_id = tc.id '
        'WHERE ur.business_id = $1 ORDER BY tc.id',
        company_id
    )
    
    builder = InlineKeyboardBuilder()
    if meters_records:
        for m in meters_records:
            t = m['name']
            n = m['number_counter']
            mid = m['id']
            icon = "❄️" if t == 'Холодная вода' else ("🔥" if t == 'Горячая вода' else "⚡")
            label = "ХВС" if t == 'Холодная вода' else ("ГВС" if t == 'Горячая вода' else "Электро")
            builder.row(
                InlineKeyboardButton(text=f"{icon} {label}: {n}", callback_data=f"editmeter_{mid}"),
                InlineKeyboardButton(text="🗑️", callback_data=f"delmeter_{mid}")
            )
    
    builder.row(InlineKeyboardButton(text="➕ Добавить счетчик", callback_data=f"addmeter_{company_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"company:{company_id}"))
    
    await callback.message.edit_text(
        "📊 <b>Управление счетчиками</b>\n\n"
        "Нажмите на счетчик чтобы изменить номер, 🗑️ чтобы удалить:",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@admin_router.callback_query(F.data.startswith("addmeter_"), StateFilter(AdminState.editing_meters))
async def add_meter_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления нового счетчика"""
    company_id = int(callback.data.split("_")[1])
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❄️ ХВС", callback_data=f"addmtype_1_{company_id}"),
        InlineKeyboardButton(text="🔥 ГВС", callback_data=f"addmtype_3_{company_id}"),
        InlineKeyboardButton(text="⚡ Электро", callback_data=f"addmtype_2_{company_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"comp_meters_{company_id}"))
    
    await callback.message.edit_text(
        "➕ <b>Добавление счетчика</b>\n\nВыберите тип:",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@admin_router.callback_query(F.data.startswith("addmtype_"), StateFilter(AdminState.editing_meters))
async def add_meter_type_selected(callback: CallbackQuery, state: FSMContext):
    """Тип счетчика выбран — ожидаем номер"""
    parts = callback.data.split("_")
    type_id = int(parts[1])
    company_id = int(parts[2])
    type_names = {1: "холодной воды", 2: "электричества", 3: "горячей воды"}
    
    await state.update_data(add_meter_type_id=type_id, meters_company_id=company_id)
    await state.set_state(AdminState.adding_meter_number)
    
    await callback.message.edit_text(
        f"📝 Введите номер счетчика {type_names.get(type_id, '')}:",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@admin_router.message(StateFilter(AdminState.adding_meter_number))
async def process_add_meter_number(message: Message, state: FSMContext, bot: Bot):
    """Обработка введённого номера нового счетчика"""
    data = await state.get_data()
    company_id = data['meters_company_id']
    type_id = data['add_meter_type_id']
    number = message.text.strip()
    
    if not number or len(number) > 25:
        await bot.send_message(message.chat.id, "❌ Некорректный номер. Попробуйте ещё раз:")
        return
    
    await new_data_insert(
        'INSERT INTO us_readings(number_counter, counter_type_id, business_id) VALUES($1, $2, $3)',
        number, type_id, company_id
    )
    
    await state.set_state(AdminState.editing_meters)
    
    # Возвращаемся к списку счетчиков — имитируем нажатие
    meters_records = await get_data(
        'SELECT ur.id, ur.number_counter, tc.name FROM us_readings ur '
        'JOIN type_counter tc ON ur.counter_type_id = tc.id '
        'WHERE ur.business_id = $1 ORDER BY tc.id',
        company_id
    )
    builder = InlineKeyboardBuilder()
    if meters_records:
        for m in meters_records:
            t = m['name']
            n = m['number_counter']
            mid = m['id']
            icon = "❄️" if t == 'Холодная вода' else ("🔥" if t == 'Горячая вода' else "⚡")
            label = "ХВС" if t == 'Холодная вода' else ("ГВС" if t == 'Горячая вода' else "Электро")
            builder.row(
                InlineKeyboardButton(text=f"{icon} {label}: {n}", callback_data=f"editmeter_{mid}"),
                InlineKeyboardButton(text="🗑️", callback_data=f"delmeter_{mid}")
            )
    builder.row(InlineKeyboardButton(text="➕ Добавить счетчик", callback_data=f"addmeter_{company_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"company:{company_id}"))
    
    await bot.send_message(
        message.chat.id,
        f"✅ Счетчик добавлен: {number}\n\n📊 <b>Управление счетчиками</b>",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@admin_router.callback_query(F.data.startswith("delmeter_"), StateFilter(AdminState.editing_meters))
async def delete_meter(callback: CallbackQuery, state: FSMContext):
    """Удаление счетчика"""
    meter_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    company_id = data['meters_company_id']
    
    await new_data_insert('DELETE FROM us_readings WHERE id = $1', meter_id)
    
    # Обновляем список
    meters_records = await get_data(
        'SELECT ur.id, ur.number_counter, tc.name FROM us_readings ur '
        'JOIN type_counter tc ON ur.counter_type_id = tc.id '
        'WHERE ur.business_id = $1 ORDER BY tc.id',
        company_id
    )
    builder = InlineKeyboardBuilder()
    if meters_records:
        for m in meters_records:
            t = m['name']
            n = m['number_counter']
            mid = m['id']
            icon = "❄️" if t == 'Холодная вода' else ("🔥" if t == 'Горячая вода' else "⚡")
            label = "ХВС" if t == 'Холодная вода' else ("ГВС" if t == 'Горячая вода' else "Электро")
            builder.row(
                InlineKeyboardButton(text=f"{icon} {label}: {n}", callback_data=f"editmeter_{mid}"),
                InlineKeyboardButton(text="🗑️", callback_data=f"delmeter_{mid}")
            )
    builder.row(InlineKeyboardButton(text="➕ Добавить счетчик", callback_data=f"addmeter_{company_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"company:{company_id}"))
    
    await callback.message.edit_text(
        "🗑️ Счетчик удалён\n\n📊 <b>Управление счетчиками</b>",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer("✅ Удалено")

@admin_router.callback_query(F.data.startswith("editmeter_"), StateFilter(AdminState.editing_meters))
async def edit_meter_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования номера счетчика"""
    meter_id = int(callback.data.split("_")[1])
    
    meter_info = await get_data(
        'SELECT ur.number_counter, tc.name FROM us_readings ur '
        'JOIN type_counter tc ON ur.counter_type_id = tc.id WHERE ur.id = $1',
        meter_id
    )
    if not meter_info:
        await callback.answer("Счетчик не найден!")
        return
    
    await state.update_data(edit_meter_id=meter_id)
    await state.set_state(AdminState.editing_meter_number)
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование счетчика</b>\n\n"
        f"Тип: {meter_info[0]['name']}\n"
        f"Текущий номер: <code>{meter_info[0]['number_counter']}</code>\n\n"
        f"Введите новый номер:",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@admin_router.message(StateFilter(AdminState.editing_meter_number))
async def process_edit_meter_number(message: Message, state: FSMContext, bot: Bot):
    """Обработка нового номера счетчика"""
    data = await state.get_data()
    meter_id = data['edit_meter_id']
    company_id = data['meters_company_id']
    new_number = message.text.strip()
    
    if not new_number or len(new_number) > 25:
        await bot.send_message(message.chat.id, "❌ Некорректный номер. Попробуйте ещё раз:")
        return
    
    await new_data_insert('UPDATE us_readings SET number_counter = $1 WHERE id = $2', new_number, meter_id)
    await state.set_state(AdminState.editing_meters)
    
    meters_records = await get_data(
        'SELECT ur.id, ur.number_counter, tc.name FROM us_readings ur '
        'JOIN type_counter tc ON ur.counter_type_id = tc.id '
        'WHERE ur.business_id = $1 ORDER BY tc.id',
        company_id
    )
    builder = InlineKeyboardBuilder()
    if meters_records:
        for m in meters_records:
            t = m['name']
            n = m['number_counter']
            mid = m['id']
            icon = "❄️" if t == 'Холодная вода' else ("🔥" if t == 'Горячая вода' else "⚡")
            label = "ХВС" if t == 'Холодная вода' else ("ГВС" if t == 'Горячая вода' else "Электро")
            builder.row(
                InlineKeyboardButton(text=f"{icon} {label}: {n}", callback_data=f"editmeter_{mid}"),
                InlineKeyboardButton(text="🗑️", callback_data=f"delmeter_{mid}")
            )
    builder.row(InlineKeyboardButton(text="➕ Добавить счетчик", callback_data=f"addmeter_{company_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"company:{company_id}"))
    
    await bot.send_message(
        message.chat.id,
        f"✅ Номер обновлён: {new_number}\n\n📊 <b>Управление счетчиками</b>",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@admin_router.callback_query(F.data.startswith('yesdeletecomp_'), StateFilter(AdminState.company_action))
@admin_router.callback_query(F.data.startswith('dontdeletecomp_'), StateFilter(AdminState.company_action))
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
    

@admin_router.callback_query(F.data.startswith("deletecomp_"), StateFilter(AdminState.company_action))
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

@admin_router.callback_query(F.data == "add_company", StateFilter(AdminState.company_list))
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
            8: ("Наименование компании", "name_company", "Введите <b>ФИО</b>:"),
            9: ("ФИО", "director_name", None)
        }
        
        field_display, field_key, next_question = steps[current_step]

        # Валидации по шагам
        if current_step == 2:  # площадь
            try:
                float(new_value)
            except ValueError:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
                except:
                    pass
                sent_msg = await message.answer(
                    text=f"<b>Шаг 2/11</b> - Введите <b>площадь</b> (в кв.м):\n\n"
                         f"❌ Площадь должна быть числом (можно с десятичной частью).\n"
                         f"Примеры: 100, 150.5, 75.2\n\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                await state.update_data(add_message_id=sent_msg.message_id)
                return
        
        elif current_step == 3:  # ставка
            try:
                float(new_value)
            except ValueError:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
                except:
                    pass
                sent_msg = await message.answer(
                    text=f"<b>Шаг 3/11</b> - Введите <b>ставку аренды</b> (руб):\n\n"
                         f"❌ Ставка должна быть числом (можно с десятичной частью).\n"
                         f"Примеры: 1000, 1500.50, 2000\n\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                await state.update_data(add_message_id=sent_msg.message_id)
                return
        
        elif current_step == 5:  # дата завершения
            try:
                input_date = datetime.strptime(new_value, "%d.%m.%Y")
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

                if input_date < today:
                    try:
                        await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
                    except:
                        pass
                    sent_msg = await message.answer(
                        text=f"<b>Шаг 5/11</b> - Введите <b>дату завершения договора</b> (ДД.ММ.ГГГГ):\n\n"
                             f"❌ Дата должна быть больше сегодняшней.\n"
                             f"Сегодня: {today.strftime('%d.%m.%Y')}\n\n"
                             f"Попробуйте снова:",
                        parse_mode=ParseMode.HTML
                    )
                    await state.update_data(add_message_id=sent_msg.message_id)
                    return
            except ValueError:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
                except:
                    pass
                sent_msg = await message.answer(
                    text=f"<b>Шаг 5/11</b> - Введите <b>дату завершения договора</b> (ДД.ММ.ГГГГ):\n\n"
                         f"❌ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ\n"
                         f"Например: 31.12.2024\n\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                await state.update_data(add_message_id=sent_msg.message_id)
                return
        
        elif current_step == 6:  # дата акта
            try:
                datetime.strptime(new_value, "%d.%m.%Y")
            except ValueError:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
                except:
                    pass
                sent_msg = await message.answer(
                    text=f"<b>Шаг 6/11</b> - Введите <b>дату акта приема-передачи</b> (ДД.ММ.ГГГГ):\n\n"
                         f"❌ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ\n"
                         f"Например: 31.12.2024\n\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                await state.update_data(add_message_id=sent_msg.message_id)
                return
        
        elif current_step == 1:  # ИНН
            check_in_existing_user = check_word_in_excel_file(new_value)
            error_text = None
            if not new_value.isdigit():
                error_text = "❌ ИНН должен содержать только цифры."
            elif len(new_value) not in [10, 12]:
                error_text = "❌ ИНН должен содержать 10 или 12 цифр."

            if error_text:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
                except:
                    pass
                sent_msg = await message.answer(
                    text=f"<b>Шаг 1/11</b> - Введите <b>ИНН</b> компании:\n\n"
                         f"{error_text}\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                await state.update_data(add_message_id=sent_msg.message_id)
                return
            if check_in_existing_user:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
                except:
                    pass
                sent_msg = await message.answer(
                    text=f"<b>Шаг 1/11</b> - Введите <b>ИНН</b> компании:\n\n"
                         f"Данный ИНН уже есть в системе\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                await state.update_data(add_message_id=sent_msg.message_id)
                return
        elif current_step == 9:  # ФИО
            error_text = None
            fio_parts = new_value.split()
            if len(fio_parts) < 3:
                error_text = "❌ Введите полное ФИО (минимум 3 слова). Пример: Иванов Иван Иванович"
            elif not re.match(r'^[а-яА-ЯёЁ\s\-]+$', new_value):
                error_text = "❌ ФИО должно содержать только буквы, пробелы и дефисы."

            if error_text:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
                except:
                    pass
                sent_msg = await message.answer(
                    text=f"<b>Шаг 9/11</b> - Введите <b>ФИО</b>:\n\n"
                         f"{error_text}\n"
                         f"Попробуйте снова:",
                    parse_mode=ParseMode.HTML
                )
                await state.update_data(add_message_id=sent_msg.message_id)
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

            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
            except:
                pass
            sent_msg = await message.answer(
                text=f"✅ <b>{field_display}</b> сохранено!\n\n"
                     f"<b>Шаг 10/11</b> - Выберите <b>форму бизнеса</b>:",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
            await state.update_data(
                new_company=new_company,
                add_step=10,
                add_message_id=sent_msg.message_id,
                business_forms=[dict(f) for f in business_forms],
            )
        else:
            # Переход к следующему шагу
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
            except:
                pass
            sent_msg = await message.answer(
                text=f"✅ <b>{field_display}</b> сохранено!\n\n"
                     f"<b>Шаг {current_step + 1}/11</b> - {next_question}",
                parse_mode=ParseMode.HTML
            )
            await state.update_data(new_company=new_company, add_step=current_step + 1, add_message_id=sent_msg.message_id)
    
    # Шаг 111 - ввод ФИО генерального директора в родительном падеже
    elif current_step == 111:
        error_text = None
        fio_parts = new_value.split()
        if len(fio_parts) < 3:
            error_text = "❌ Введите полное ФИО (минимум 3 слова). Пример: Иванова Ивана Ивановича"
        elif not re.match(r'^[а-яА-ЯёЁ\s\-]+$', new_value):
            error_text = "❌ ФИО должно содержать только буквы, пробелы и дефисы."

        if error_text:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
            except:
                pass
            sent_msg = await message.answer(
                text=f"<b>Шаг 12/13</b> - Введите <b>ФИО руководителя в родительном падеже</b>:\n\n"
                     f"{error_text}\n"
                     f"Попробуйте снова:",
                parse_mode=ParseMode.HTML
            )
            await state.update_data(add_message_id=sent_msg.message_id)
            return
            
        new_company['director_fio_genitive'] = new_value
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
        except:
            pass
        sent_msg = await message.answer(
            text=f"✅ <b>ФИО руководителя</b> сохранено!\n\n"
                 f"<b>Шаг 13/13</b> - Введите <b>вид деятельности</b>:",
            parse_mode=ParseMode.HTML
        )
        await state.update_data(new_company=new_company, add_step=10, add_message_id=sent_msg.message_id)

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
        director_title = new_company.get('director_title')
        director_fio_genitive = new_company.get('director_fio_genitive')
        director_title_line = f"\n            👔 <b>Должность:</b> {director_title}" if director_title else ""
        director_genitive_line = f"\n            👤 <b>ФИО в Р.П.:</b> {director_fio_genitive}" if director_fio_genitive else ""
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
            👤 <b>ФИО:</b> {sfp_general_direcotr}{director_title_line}{director_genitive_line}
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
        await new_data_insert('INSERT INTO bussines(name_company, id_form, square, bid, acceptance_certificate, agreement, end_date_agreement, id_type_of_activity, sheet_name, surname, first_name, patronymic, phone, director_title, director_fio_genitive) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)', 
                            name_company, id_form_doing, square, bid, acceptance_certificate, agreement, end_agreement, id_toa, list_name, gen_dir_list[0], gen_dir_list[1], gen_dir_list[2], phone, director_title, director_fio_genitive)
        

        # ========== ИНТЕГРАЦИЯ С НОВЫМ РОУТЕРОМ ==========
        
        records_ids = await get_data('SELECT id FROM bussines WHERE name_company = $1 AND square = $2',name_company,square)
        for business in records_ids:
            company_id = business['id']
        # Очищаем возможные старые данные для этой компании
        if company_id in temp_meter_data:
            del temp_meter_data[company_id]
        
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=add_message_id)
        except:
            pass
            
        # Клавиатура с вопросом о счетчиках
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Я", callback_data=f"meter_filler_admin")],
            [InlineKeyboardButton(text="🏢 Арендатор", callback_data="meter_filler_tenant")],
            [InlineKeyboardButton(text="⏭️ Пропустить (без счетчиков)", callback_data="meter_skip")],
        ])
        
        sent_msg = await message.answer(
            text="✅ <b>Компания успешно создана!</b>\n\n"
                 "Добавить номера счетчиков?\n"
                 "• ❄️ Холодная вода\n"
                 "• 🔥 Горячая вода\n"
                 "• ⚡️ Электричество\n\n"
                 "<i>Номера можно будет добавить позже в настройках компании.</i>\n\n"
                 "Кто будет заполнять номера?",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

        # Сохраняем данные в state для возврата
        await state.update_data(
            company_id=company_id,
            return_text=company_info,
            return_message_id=sent_msg.message_id,
            add_message_id=sent_msg.message_id
        )
        
        # Устанавливаем состояние выбора заполнителя (из вашего admin_states.py)
        await state.set_state(AdminState.meter_filler_choice)
        
        await state.set_state(AdminState.meter_filler_choice)


@admin_router.callback_query(F.data.startswith("form:"))
async def select_business_form(callback: CallbackQuery, state: FSMContext):
    form_id = int(callback.data.split(":")[1])
    
    data = await state.get_data()
    new_company = data.get("new_company", {})
    add_message_id = data.get("add_message_id")
    
    new_company['id_form'] = form_id
    
    from main import bot
    try:
        await bot.delete_message(chat_id=callback.message.chat.id, message_id=add_message_id)
    except:
        pass

    if form_id == 1:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Генеральный директор", callback_data="director_title:Генеральный директор")],
            [InlineKeyboardButton(text="Директор", callback_data="director_title:Директор")],
            [InlineKeyboardButton(text="🔙 Назад к формам", callback_data="back_to_forms")],
        ])
        sent_msg = await callback.message.answer(
            text=f"✅ <b>Форма бизнеса</b> выбрана!\n\n"
                 f"<b>Шаг 11/12</b> - Выберите <b>должность руководителя</b>:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.update_data(new_company=new_company, add_message_id=sent_msg.message_id)
    else:
        sent_msg = await callback.message.answer(
            text=f"✅ <b>Форма бизнеса</b> выбрана!\n\n"
                 f"<b>Шаг 11/11</b> - Введите <b>вид деятельности</b>:",
            parse_mode=ParseMode.HTML
        )
        await state.update_data(new_company=new_company, add_step=10, add_message_id=sent_msg.message_id)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("director_title:"))
async def select_director_title(callback: CallbackQuery, state: FSMContext):
    title = callback.data.split(":", 1)[1]

    data = await state.get_data()
    new_company = data.get("new_company", {})
    add_message_id = data.get("add_message_id")

    new_company['director_title'] = title

    from main import bot
    try:
        await bot.delete_message(chat_id=callback.message.chat.id, message_id=add_message_id)
    except:
        pass

    sent_msg = await callback.message.answer(
        text=f"✅ <b>Должность руководителя</b> выбрана: {title}\n\n"
             f"<b>Шаг 12/13</b> - Введите <b>ФИО руководителя в родительном падеже</b> ('в лице кого?'):\n"
             f"<i>Пример: Иванова Ивана Ивановича</i>",
        parse_mode=ParseMode.HTML
    )
    await state.update_data(new_company=new_company, add_step=111, add_message_id=sent_msg.message_id)
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
    WHERE EXISTS (
        SELECT 1 FROM us_readings ur WHERE ur.business_id = b.id
    )
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
    """Начать редактирование ставки холодной воды"""
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
        f"✏️ Редактирование ставки\n\n"
        f"Текущее значение: {current_tariff} руб./м³\n\n"
        f"Введите новую ставку (в рублях за м³):\n"
        f"(например: 45.50)",
        reply_markup=cancel_keyboard(with_edit_option=True),
        parse_mode="HTML"
    )
    await call.answer()


# Обработчик для РЕДАКТИРОВАНИЯ ставки
@admin_router.message(StateFilter(AdminState.waiting_for_tariff_edit))
async def process_tariff_edit_input(message: Message, state: FSMContext, bot: Bot):
    """Обработка введенной ставки при РЕДАКТИРОВАНИИ"""
    if message.chat.id != ADMIN_CHAT_ID:
        return
    if not message.text:
        return

    raw_text = message.text.replace(",", ".")
    
    try:
        tariff = float(raw_text)
        if tariff < 0:
            raise ValueError
    except ValueError:
        await _admin_try_delete_user_message(bot, message)
        await send_to_admin_topic(
            bot,
            "⚠️ Ошибка ввода\n\n"
            "Пожалуйста, введите корректную ставку (положительное число).",
            reply_markup=cancel_keyboard()
        )
        return
    
    data = await state.get_data()
    edit_type = data.get("edit_type")
    last_msg_id = data.get("last_msg_id")  # Получаем ID последнего сообщения бота
    
    # Сохраняем ставку
    global collected_data
    if edit_type not in collected_data:
        collected_data[edit_type] = {}
    
    collected_data[edit_type]["tariff"] = tariff
    
    # Возвращаемся в меню редактирования
    await state.set_state(AdminState.editing_data)
    
    names = get_type_names()
    label = names.get(edit_type, "")
    
    builder = InlineKeyboardBuilder()
    
    # Для холодной воды - только ставка
    builder.button(text="💰 Редактировать ставку", callback_data=f"admin_edit_tariff_{edit_type}")
    builder.button(text="🔙 Назад к списку", callback_data="admin_edit_menu")
    builder.adjust(1)
    
    type_data = collected_data.get(edit_type, {})
    
    # Пытаемся отредактировать последнее сообщение бота
    if last_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=ADMIN_CHAT_ID,
                message_id=last_msg_id,
                text=f"✅ Ставка обновлена!\n\n"
                     f"✏️ Редактирование показаний {label}\n\n"
                     f"Текущие значения:\n"
                     f"• Ставка: {type_data.get('tariff', '—')} руб./м³\n\n"
                     f"Что вы хотите изменить?",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка редактирования: {e}")
            # Если не получилось отредактировать, отправляем новое сообщение
            new_msg = await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"✅ Ставка обновлена!\n\n"
                     f"✏️ Редактирование показаний {label}\n\n"
                     f"Текущие значения:\n"
                     f"• Ставка: {type_data.get('tariff', '—')} руб./м³\n\n"
                     f"Что вы хотите изменить?",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            await state.update_data(last_msg_id=new_msg.message_id)
    else:
        # Если нет last_msg_id, отправляем новое сообщение
        new_msg = await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"✅ Ставка обновлена!\n\n"
                 f"✏️ Редактирование показаний {label}\n\n"
                 f"Текущие значения:\n"
                 f"• Ставка: {type_data.get('tariff', '—')} руб./м³\n\n"
                 f"Что вы хотите изменить?",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await state.update_data(last_msg_id=new_msg.message_id)
    
    await _admin_try_delete_user_message(bot, message)


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
    
    await state.set_state(AdminState.waiting_for_heat_amount)
    
    await edit_admin_message(
        bot,
        call.message.message_id,
        f"🔥 Отопление - {name_company}\n\n"
        f"Введите сумму с НДС (в рублях):\n"
        f"(например: 1250.75)",
        parse_mode="HTML"
    )
    await call.answer()


# heat_volume_input удалён — ввод показаний счётчика для отопления больше не используется (треб. 18)



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
        await state.update_data(heat_amount=amount, heat_volume=0) # Обнуляем объем (треб. 18)
        await state.set_state(AdminState.waiting_for_unexpected_individual)
        
        data = await state.get_data()
        tenant_name = data.get('selected_tenant_name', 'Арендатор')
        
        await message.answer(
            f"✅ Сумма отопления: {amount} руб.\n\n"
            f"💰 <b>Непредвиденные расходы</b> - {tenant_name}\n"
            f"Введите сумму (в рублях) или 0 если их нет:\n"
            f"(например: 500)",
            parse_mode="HTML"
        )
    else:
        await message.answer('Пожалуйста введите корректное значение')


@admin_router.message(StateFilter(AdminState.waiting_for_unexpected_individual))
async def unexpected_individual_input(message: Message, state: FSMContext, bot: Bot):
    """Ввод индивидуальных непредвиденных расходов"""
    try:
        amount = float(message.text.strip().replace(',', '.'))
        amount = round(amount, 2)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму (например: 500.00).")
        return
        
    await state.update_data(unexpected_individual=amount)
    await state.set_state(AdminState.waiting_for_expl_individual)
    
    data = await state.get_data()
    tenant_name = data.get('selected_tenant_name', 'Арендатор')
    
    await message.answer(
        f"✅ Непредвиденные расходы: {amount} руб.\n\n"
        f"🏢 <b>Коммунальные услуги</b> - {tenant_name}\n"
        f"Введите сумму (в рублях) или 0 если их нет:\n"
        f"(например: 1200)",
        parse_mode="HTML"
    )


@admin_router.message(StateFilter(AdminState.waiting_for_expl_individual))
async def expl_individual_input(message: Message, state: FSMContext, bot: Bot):
    """Ввод индивидуальных эксплуатационных услуг"""
    try:
        amount = float(message.text.strip().replace(',', '.'))
        amount = round(amount, 2)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму (например: 1200.00).")
        return
        
    await state.update_data(expl_individual=amount)
    await state.set_state(AdminState.confirming_readings)
    
    data = await state.get_data()
    tenant_name = data.get('selected_tenant_name', 'Арендатор')
    tenant_id = data.get('selected_tenant_id')
    heat_amount = data.get('heat_amount', 0)
    unexpected = data.get('unexpected_individual', 0)
    
    await message.answer(
        f"📊 <b>Проверьте введенные данные:</b>\n\n"
        f"🏢 Арендатор: {tenant_name}\n"
        f"🔥 Отопление: {heat_amount:.2f} ₽\n"
        f"💰 Непредвиденные: {unexpected:.2f} ₽\n"
        f"🏢 Коммунальные услуги: {amount:.2f} ₽\n\n"
        f"Все верно?",
        reply_markup=confirm_readings_keyboard(tenant_id),
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data.startswith("savetenant_readings_"), StateFilter(AdminState.confirming_readings))
async def save_readings(call: CallbackQuery, state: FSMContext):
    from main import bot
    from handlers.excel_tg_test import add_tenant_for_user
    import asyncio
    import locale
    from datetime import datetime, timedelta
    
    tenant_id = int(call.data.split("_")[2])
    data = await state.get_data()
    volume = data.get('heat_volume', 0)
    amount = data.get('heat_amount', 0)
    unexpected = data.get('unexpected_individual', 0)
    expl = data.get('expl_individual', 0)
    
    # Сохраняем показания арендатора
    await add_tenant_for_user(tenant_id, volume=volume, amount=amount, exploitation=expl, unexpected=unexpected)
    
    # Обновляем список обработанных арендаторов
    data = await state.get_data()
    items = data.get('list_tenant', [])
    items.append(tenant_id)
    await state.update_data(list_tenant=items)
    new_data = await state.get_data()
    new_items = new_data.get('list_tenant', [])
    await state.set_state(AdminState.selecting_tenant)
    
    # Получаем список арендаторов из БД (только те, у кого есть счётчики)
    query = """
    SELECT b.id
    FROM bussines b
    WHERE EXISTS (SELECT 1 FROM us_readings ur WHERE ur.business_id = b.id)
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
    required = ['electro', 'water_cold', 'drainage']
    missing = []
    names = {
        'electro': '⚡ Электроэнергия',
        'water_cold': '🚰 Холодная вода',
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
        'drainage': '💧 Водоотведение'
    }
    
    for req in required:
        if req in collected_data:
            data = collected_data[req]
            label = display_names[req]
            report += f"{label}\n"
            
            if req == 'water_cold':
                report += f"• Ставка: {data.get('tariff', 0)} руб./м³\n\n"
            elif req == 'drainage':
                report += f"• Сумма: {data.get('amount', 0)} руб.\n\n"
            else:  # electro
                report += f"• Объем: {data.get('volume', 0)}\n"
                report += f"• Сумма: {data.get('amount', 0)} руб.\n\n"
    
    # Кнопки для выбора
    builder = InlineKeyboardBuilder()
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


# ── /rip_id — удаление пользователя (отвязка от компании) ──────────────

RIP_PER_PAGE = 8


async def _build_rip_user_list(page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    query = """
    SELECT u.user_id, u.username, u.first_name, u.second_name,
           b.name_company
    FROM users u
    LEFT JOIN bussines b ON b.id = u.id_business
    ORDER BY b.name_company NULLS LAST, u.user_id
    """
    users = await get_data(query) or []
    total = len(users)

    if total == 0:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Закрыть", callback_data="rip_close"))
        return "🗑 <b>Удаление пользователя</b>\n\nНет зарегистрированных пользователей.", builder.as_markup()

    start = page * RIP_PER_PAGE
    end = start + RIP_PER_PAGE
    page_users = users[start:end]
    total_pages = (total + RIP_PER_PAGE - 1) // RIP_PER_PAGE

    builder = InlineKeyboardBuilder()
    for u in page_users:
        uid = u["user_id"]
        company = u.get("name_company") or "без компании"
        uname = u.get("username") or ""
        label = f"{company}"
        if uname:
            label += f" (@{uname})"
        if len(label) > 40:
            label = label[:38] + "…"
        builder.row(InlineKeyboardButton(text=label, callback_data=f"ripusr:{uid}"))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"rippage_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if end < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"rippage_{page + 1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🔙 Закрыть", callback_data="rip_close"))

    text = f"🗑 <b>Удаление пользователя</b> ({total})\n\nВыберите пользователя для удаления:"
    return text, builder.as_markup()


@admin_router.message(Command("rip_id"))
async def rip_id_command(message: Message, state: FSMContext):
    if not await has_admin_access(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        return

    await state.clear()
    await state.set_state(AdminState.rip_id_list)
    text, kb = await _build_rip_user_list(0)
    await message.answer(text=text, reply_markup=kb, parse_mode=ParseMode.HTML)


@admin_router.callback_query(F.data.startswith("rippage_"), StateFilter(AdminState.rip_id_list))
async def rip_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[1])
    text, kb = await _build_rip_user_list(page)
    await callback.message.edit_text(text=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("ripusr:"), StateFilter(AdminState.rip_id_list))
async def rip_user_selected(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split(":")[1]

    query = """
    SELECT u.user_id, u.username, u.first_name, u.second_name, u.patronymic,
           u.phone_number, b.name_company
    FROM users u
    LEFT JOIN bussines b ON b.id = u.id_business
    WHERE u.user_id = $1
    """
    rows = await get_data(query, user_id)
    if not rows:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    u = dict(rows[0])
    fio_parts = [
        str(u.get("second_name") or "").strip(),
        str(u.get("first_name") or "").strip(),
        str(u.get("patronymic") or "").strip(),
    ]
    fio = " ".join(p for p in fio_parts if p) or "не указано"
    uname = u.get("username") or "не указан"
    company = u.get("name_company") or "не привязан"

    lines = [
        "🗑 <b>Подтверждение удаления</b>\n",
        f"🆔 <b>Telegram ID:</b> <code>{u['user_id']}</code>",
        f"📱 <b>Username:</b> @{uname}" if uname != "не указан" else f"📱 <b>Username:</b> {uname}",
        f"👤 <b>ФИО:</b> {fio}",
        f"🏢 <b>Компания:</b> {company}",
        "\n⚠️ <b>Вы уверены, что хотите удалить этого пользователя?</b>\n"
        "<i>Пользователь сможет заново пройти регистрацию.</i>",
    ]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"ripconfirm:{user_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="ripcancel"),
        ],
    ])

    await state.set_state(AdminState.rip_id_confirm)
    await callback.message.edit_text(
        text="\n".join(lines),
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("ripconfirm:"), StateFilter(AdminState.rip_id_confirm))
async def rip_confirm(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split(":")[1]

    result = await new_data_insert('DELETE FROM users WHERE user_id = $1', user_id)
    if result is None:
        await callback.answer("Ошибка при удалении", show_alert=True)
        return

    await state.set_state(AdminState.rip_id_list)
    text, kb = await _build_rip_user_list(0)
    header = f"✅ Пользователь <code>{user_id}</code> удалён.\n\n"
    await callback.message.edit_text(text=header + text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@admin_router.callback_query(F.data == "ripcancel", StateFilter(AdminState.rip_id_confirm))
async def rip_cancel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.rip_id_list)
    text, kb = await _build_rip_user_list(0)
    await callback.message.edit_text(text=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@admin_router.callback_query(F.data == "rip_close", StateFilter(AdminState.rip_id_list))
async def rip_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🗑 Удаление пользователя — завершено.")
    await callback.answer()
