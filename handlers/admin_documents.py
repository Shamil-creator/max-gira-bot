import asyncio
import logging
import locale
import os
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from datetime import datetime
from states.admin_states import AdminState
from handlers.admin_group import admin_main_keyboard, tenants_keyboard, admin_router
from handlers.config import config
from handlers.excel_tg_test import add_tenant_for_user,admin_indicators
from handlers.excel_tg_test import admin_indicators, create_excel, get_volume_and_amount_month, count_tenant_excel,create_word
from datetime import datetime, timedelta
from aiogram.types.input_file import FSInputFile
import asyncpg


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

# Хранилище для файлов
temp_documents = {}

def create_document_keyboard(has_files: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для управления документами"""
    buttons = []
    
    if has_files:
        buttons.append([InlineKeyboardButton(text="📎 Добавить еще", callback_data="add_more_docs")])
        buttons.append([InlineKeyboardButton(text="✅ Отправить с документами", callback_data="send_with_docs")])
        buttons.append([InlineKeyboardButton(text="📤 Отправить без документов", callback_data="skip_documents")])
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_docs")])
    else:
        buttons.append([InlineKeyboardButton(text="📎 Добавить файл", callback_data="add_document")])
        buttons.append([InlineKeyboardButton(text="📤 Отправить без документов", callback_data="skip_documents")])
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_docs")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@admin_router.callback_query(F.data.startswith("savetenant_readings_"), F.data.contains("_"))
async def save_readings_with_docs(call: CallbackQuery, state: FSMContext):
    """Сохранение показаний с запросом документов"""
    from main import bot
    
    tenant_id = int(call.data.split("_")[2])
    data = await state.get_data()
    volume = data.get('heat_volume')
    amount = data.get('heat_amount')
    
    # Сохраняем показания арендатора
    await add_tenant_for_user(tenant_id, volume=volume, amount=amount)
    
    # Обновляем список обработанных
    data = await state.get_data()
    items = data.get('list_tenant', [])
    items.append(tenant_id)
    await state.update_data(list_tenant=items)
    
    new_data = await state.get_data()
    new_items = new_data.get('list_tenant', [])
    
    # Проверяем, все ли арендаторы обработаны
    query = "SELECT b.id FROM bussines b ORDER BY b.name_company"
    users_records = await get_data(query)
    list_ids = [user['id'] for user in users_records]
    
    if sorted(list_ids) == sorted(new_items):
        # Все арендаторы обработаны - запрашиваем документы
        await state.set_state(AdminState.waiting_for_documents)
        
        # Сохраняем ID для возврата
        await state.update_data(
            return_message_id=call.message.message_id,
            return_chat_id=call.message.chat.id
        )
        
        # Инициализируем хранилище документов
        business_id = data.get('business_id', tenant_id)
        temp_documents[business_id] = {
            'files': [],
            'message_id': call.message.message_id,
            'chat_id': call.message.chat.id
        }
        await state.update_data(business_id=business_id)
        
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📎 <b>Подтверждающие документы</b>\n\n"
                 "Прикрепите подтверждающие документы (счета, акты, накладные) для рассылки.\n"
                 "Можно прикрепить несколько файлов.",
            reply_markup=create_document_keyboard(has_files=False),
            parse_mode=ParseMode.HTML
        )
    else:
        # Еще есть арендаторы
        keyboard = await tenants_keyboard(new_items, page=0)
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Показания сохранены!\n\n"
                 f"🔥 Отопление\n\n"
                 f"Выберите следующего арендатора:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    
    await call.answer()

@admin_router.callback_query(F.data == "add_document", AdminState.waiting_for_documents)
async def add_document_prompt(call: CallbackQuery, state: FSMContext):
    """Запрос на добавление документа"""
    await call.message.edit_text(
        "📎 <b>Отправьте файл</b>\n\n"
        "Поддерживаются любые форматы:\n"
        "📄 PDF, DOC, DOCX\n"
        "🖼️ JPG, PNG (отправьте изображение именно как фото, а не файлом)\n"
        "📊 XLS, XLSX\n\n"
        "После отправки файла появится меню.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_docs_menu")]
        ]),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.confirming_documents)
    await call.answer()

@admin_router.message(AdminState.confirming_documents, F.document)
async def process_document(message: Message, state: FSMContext):
    """Обработка полученного документа"""
    data = await state.get_data()
    business_id = data.get('business_id')
    
    if business_id not in temp_documents:
        temp_documents[business_id] = {'files': []}
    
    file_info = {
        'file_id': message.document.file_id,
        'file_name': message.document.file_name,
        'file_size': message.document.file_size,
        'mime_type': message.document.mime_type
    }
    
    temp_documents[business_id]['files'].append(file_info)
    
    # Показываем обновленное меню
    file_list = "\n".join([f"📄 {f['file_name']}" for f in temp_documents[business_id]['files']])
    
    await message.answer(
        f"✅ <b>Файл добавлен!</b>\n\n"
        f"<b>Загруженные файлы:</b>\n{file_list}\n\n"
        f"Можете добавить еще или отправить.",
        reply_markup=create_document_keyboard(has_files=True),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.waiting_for_documents)

@admin_router.message(AdminState.confirming_documents, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка полученного фото"""
    data = await state.get_data()
    business_id = data.get('business_id')
    
    if business_id not in temp_documents:
        temp_documents[business_id] = {'files': []}
    
    photo = message.photo[-1]
    file_info = {
        'file_id': photo.file_id,
        'file_name': f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
        'file_size': photo.file_size,
        'mime_type': 'image/jpeg'
    }
    
    temp_documents[business_id]['files'].append(file_info)
    
    file_list = "\n".join([f"🖼️ {f['file_name']}" for f in temp_documents[business_id]['files']])
    
    await message.answer(
        f"✅ <b>Фото добавлено!</b>\n\n"
        f"<b>Загруженные файлы:</b>\n{file_list}\n\n"
        f"Можете добавить еще или отправить.",
        reply_markup=create_document_keyboard(has_files=True),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.waiting_for_documents)

@admin_router.callback_query(F.data == "add_more_docs", AdminState.waiting_for_documents)
async def add_more_docs(call: CallbackQuery, state: FSMContext):
    """Добавление еще документов"""
    await add_document_prompt(call, state)

@admin_router.callback_query(F.data == "back_to_docs_menu", AdminState.confirming_documents)
async def back_to_docs_menu(call: CallbackQuery, state: FSMContext):
    """Возврат в меню документов"""
    data = await state.get_data()
    business_id = data.get('business_id')
    
    await state.set_state(AdminState.waiting_for_documents)
    
    if business_id in temp_documents and temp_documents[business_id]['files']:
        file_list = "\n".join([f"📄 {f['file_name']}" for f in temp_documents[business_id]['files']])
        text = f"📎 <b>Подтверждающие документы</b>\n\n<b>Загруженные файлы:</b>\n{file_list}"
    else:
        text = "📎 <b>Подтверждающие документы</b>\n\nПрикрепите подтверждающие документы."
    
    await call.message.edit_text(
        text,
        reply_markup=create_document_keyboard(has_files=bool(temp_documents.get(business_id, {}).get('files'))),
        parse_mode=ParseMode.HTML
    )
    await call.answer()

@admin_router.callback_query(F.data == "skip_documents")
async def skip_documents(call: CallbackQuery, state: FSMContext):
    """Отправить без документов"""
    await proceed_with_sending(call, state, documents=[])

@admin_router.callback_query(F.data == "send_with_docs")
async def send_with_documents(call: CallbackQuery, state: FSMContext):
    """Отправить с документами"""
    data = await state.get_data()
    business_id = data.get('business_id')
    
    documents = temp_documents.get(business_id, {}).get('files', [])
    await proceed_with_sending(call, state, documents)

@admin_router.callback_query(F.data == "cancel_docs")
async def cancel_documents(call: CallbackQuery, state: FSMContext):
    """Отмена отправки"""
    data = await state.get_data()
    business_id = data.get('business_id')
    
    if business_id in temp_documents:
        del temp_documents[business_id]
    
    await state.clear()
    await call.message.edit_text(
        "❌ Отправка отменена",
        reply_markup=admin_main_keyboard()
    )
    await call.answer()

async def proceed_with_sending(call: CallbackQuery, state: FSMContext, documents: list):
    """Финальная отправка с документами и анимацией"""
    from main import bot
    
    data = await state.get_data()
    collected_data = data.get('collected_data', {})
    
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
    prev_month_name_en = prev.strftime("%B")
    prev_year = prev.strftime("%Y")
    
    try:
        locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
        prev_month_name_ru = prev.strftime("%B").capitalize()
    except:
        prev_month_name_ru = prev_month_name_en
    
    period_str = f"{prev_month_name_ru} {prev_year}"
    info_list = [end, start, end, period_str]
    
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
    
    # Предварительно скачиваем все приложенные документы один раз, 
    # чтобы не скачивать их заново для каждого пользователя (это надежнее и быстрее)
    prepared_docs = []
    if documents:
        import aiohttp, os as _os
        async with aiohttp.ClientSession() as session:
            for doc in documents:
                if isinstance(doc['file_id'], str) and doc['file_id'].startswith("http"):
                    try:
                        async with session.get(doc['file_id']) as resp:
                            if resp.status == 200:
                                media_bytes = await resp.read()
                                from aiogram.types.input_file import BufferedInputFile
                                # Передаём полное имя файла с расширением.
                                # maxapi теперь умеет сохранять оригинальное расширение (xlsx, pdf, docx...)
                                original_name = doc['file_name'] or "document"
                                prepared_docs.append(BufferedInputFile(media_bytes, filename=original_name))
                                continue
                    except Exception as e:
                        logging.error(f"Ошибка предварительного скачивания документа {doc['file_name']}: {e}")
                # Если не скачалось или не URL, используем как есть
                prepared_docs.append(doc)

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
        text_for_user = await get_volume_and_amount_month(user)
        file = await create_word(collected_data, user, count_users, info_list)
        
        from handlers.run import get_form_of_doing_info_business
        fod_name = await get_form_of_doing_info_business(user)
        nice_filename = f"Акт расчета КУ {fod_name} {period_str}.docx"
        document = FSInputFile(file, filename=nice_filename)
        
        await bot.send_document(
            chat_id=int(user),
            document=document,
            caption='🧾 Ваш счёт за прошедший месяц'
        )
        os.unlink(file)
        
        # Отправляем приложенные документы
        for doc in prepared_docs:
            if isinstance(doc, dict):
                # Если это не скачанный файл, а исходный словарь
                await bot.send_document(
                    chat_id=int(user),
                    document=doc['file_id'],
                    caption=f"📎 Подтверждающий документ: {doc['file_name']}",
                    filename=doc['file_name']
                )
            else:
                # Если это BufferedInputFile
                await bot.send_document(
                    chat_id=int(user),
                    document=doc,
                    caption=f"📎 Подтверждающий документ: {doc.filename}"
                )
        
        await bot.send_message(chat_id=int(user), text=text_for_user)
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
    business_id = data.get('business_id')
    if business_id in temp_documents:
        del temp_documents[business_id]
    
    # Финальный отчет
    report = "✅ <b>Все показания успешно сохранены и отправлены!</b>\n\n"
    
    names = {
        "electro": "⚡ Электроэнергия",
        "water_cold": "🚰 Холодная вода", 
        "water_hot": "🔥 Горячая вода",
        "expl": "🏢 Комм. услуги",
        "drainage": "💧 Водоотведение",
        "heating": "🔥 Отопление"
    }
    
    for reading_type, data in collected_data.items():
        label = names.get(reading_type, reading_type)
        report += f"{label}\n"
        
        if reading_type == 'heating':
            report += f"• Объем: {data.get('volume', 0)}\n"
            report += f"• Сумма: {data.get('amount', 0)} руб.\n\n"
        elif reading_type in ['expl', 'drainage']:
            report += f"• Сумма: {data['amount']} руб.\n\n"
        else:
            report += f"• Объем: {data['volume']}\n"
            report += f"• Сумма: {data['amount']} руб.\n\n"
    
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
    
    await state.clear()
    await call.answer("✅ Рассылка завершена!")