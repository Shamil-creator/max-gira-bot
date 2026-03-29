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
from aiogram.types.input_file import FSInputFile
import asyncpg
from handlers.config import config
from aiogram.fsm.state import State
from aiogram.fsm.context import FSMContext
import psycopg2
from aiogram.types import InputMediaPhoto, InputMediaVideo, FSInputFile
from states.auth_states import Auth_States
from states.technical_request_states import Technical_States

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

technical_request_router = Router()

def get_keyboard_technical():
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text='Только текст', callback_data='only_text_cb')]]
    )
    return keyboard

def get_send_keyboard_technical():
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text='Отправить', callback_data='send_technical_request_cb')]]
    )
    return keyboard

async def get_info_business(id):
    us_businesses = await get_data('SELECT b.* FROM users u RIGHT JOIN Bussines b ON b.id = u.id_business WHERE u.User_Id = $1', str(id))
    return us_businesses

@technical_request_router.message(Technical_States.get_problem_state)
async def get_cleint_problem(msg: Message, state: FSMContext):
    problem = msg.text
    await state.update_data(problem=problem)
    await state.update_data(media_files=[])
    await state.set_state(Technical_States.wait_image_state)
    await msg.answer('Пожалуйста пришлите фото или видео проблемы.\n\nЕсли вы хотите оставить только текст, то нажмите кнопку ниже👇',reply_markup=get_keyboard_technical())

@technical_request_router.callback_query(F.data.in_(['only_text_cb']))
async def get_cb(call: CallbackQuery, state: FSMContext):
    from main import bot
    from handlers.config import config
    id_chat = config.chanel_id.get_secret_value()
    user_data = await state.get_data()
    problem_text = user_data.get('problem')
    data = call.data
    id_us = call.message.chat.id
    await call.message.delete()
    if data == 'only_text_cb':
        records_list = await get_info_business(id_us)
        print(records_list)
        if records_list:
            for list in records_list:
                name = list['name_company']

        all_message = f'[ТЕХЗАЯВКА] От арендатора {name}\nCообщение: {problem_text}'
        await bot.send_message(chat_id=id_chat, text=all_message)
        await call.message.answer('Ваше обращение было передано')
        from handlers.run import build_menu_keyboard
        await state.set_state(Auth_States.menu_state)
        await call.message.answer('Вы в меню', reply_markup=await build_menu_keyboard(id_us))

@technical_request_router.callback_query(F.data.in_(['send_technical_request_cb']))
async def call(call: CallbackQuery, state: FSMContext):
    from main import bot
    from handlers.run import build_menu_keyboard
    from handlers.config import config
    id_chat = config.chanel_id.get_secret_value()
    id_us = call.message.chat.id
    # инфо арендатора
    user_data = await state.get_data()
    problem_text = user_data.get('problem')
    data = await state.get_data()
    records_list = await get_info_business(id_us)
    print(records_list)
    if records_list:
        for list in records_list:
            name = list['name_company']

        all_message = f'[ТЕХЗАЯВКА] От арендатора {name}\nCообщение: {problem_text}'
    media_files = data.get('media_files', [])
    media_group = []
    await call.message.delete()
    for i, media in enumerate(media_files):
        if media['type'] == 'photo':
            media_group.append(
                InputMediaPhoto(
                    media=media['file_id'],
                    caption=f"[ТЕХЗАЯВКА] 📸 Фото {i+1}\n{all_message}" if i == 0 else ""
                )
            )
        elif media['type'] == 'video':
            media_group.append(
                InputMediaVideo(
                    media=media['file_id'],
                    caption=f"[ТЕХЗАЯВКА] 🎥 Видео {i+1} от пользователя\n{all_message}" if i == 0 else ""
                )
            )
    await call.message.answer('Ваше обращение было передано')
    await state.set_state(Auth_States.menu_state)
    await call.message.answer('Вы в меню', reply_markup=await build_menu_keyboard(id_us))
    try:
        await bot.send_media_group(
            chat_id=id_chat,
            media=media_group
        )
        await state.update_data(media_files=[])
    except Exception as e:
        print(f"Ошибка при отправке медиагруппы: {e}")
        for media in media_files:
            try:
                if media['type'] == 'photo':
                    await bot.send_photo(
                        chat_id=id_chat,
                        photo=media['file_id'],
                        caption=f"[ТЕХЗАЯВКА] 📸 Фото от пользователя\n{all_message}"
                    )
                elif media['type'] == 'video':
                    await bot.send_video(
                        chat_id=id_chat,
                        video=media['file_id'],
                        caption=f"[ТЕХЗАЯВКА] 🎥 Видео от пользователя\n{all_message}"
                    )
                await state.update_data(media_files=[])
            except Exception as e:
                print(f"Ошибка при отправке отдельного файла: {e}")

@technical_request_router.message(Technical_States.wait_image_state)
async def get_client_problem(msg: Message, state: FSMContext):
    from main import bot
    from handlers.config import config
    
    id_admin = config.chanel_id.get_secret_value()
    
    data = await state.get_data()
    media_files = data.get('media_files', [])
    
    if len(media_files) >= 5:
        await msg.answer("❌ Вы уже добавили максимальное количество файлов (5). Нажмите 'Отправить' для продолжения.",reply_markup=get_send_keyboard_technical())
        return
    
    if msg.photo or msg.video:
        if msg.photo:
            file_id = msg.photo[-1].file_id
            file_type = 'photo'
        elif msg.video:
            file_id = msg.video.file_id
            file_type = 'video'
        
        media_files.append({'file_id': file_id, 'type': file_type})
        await state.update_data(media_files=media_files)
        
        remaining_files = 5 - len(media_files)
        await msg.answer(f"✅ Файл добавлен! Вы можете добавить еще {remaining_files} файлов или нажмите 'Отправить' для продолжения.",reply_markup=get_send_keyboard_technical())
    else:
        await msg.answer('Пожалуйста, отправьте фото или видео, либо нажмите кнопку "Отправить"',reply_markup=get_send_keyboard_technical())
    
    # Переходим к следующему состоянию
    # await state.set_state(Technical_States.next_state)

# Добавьте обработчик для просмотра текущих файлов
@technical_request_router.message(F.text == "Показать файлы")
async def show_current_files(msg: Message, state: FSMContext):
    data = await state.get_data()
    media_files = data.get('media_files', [])
    
    if not media_files:
        await msg.answer("📁 Вы еще не добавили файлов.")
    else:
        file_types = {
            'photo': '📸 Фото',
            'video': '🎥 Видео'
        }
        files_list = "\n".join([f"{file_types[file['type']]} {i+1}" for i, file in enumerate(media_files)])
        await msg.answer(f"📁 Текущие файлы ({len(media_files)}/5):\n{files_list}")


@technical_request_router.message(F.text == "Очистить файлы")
async def clear_files(msg: Message, state: FSMContext):
    await state.update_data(media_files=[])
    await msg.answer("🗑️ Все файлы очищены. Вы можете начать заново.")

# @technical_request_router.message(Technical_States.wait_image_state)
# async def get_cleint_problem(msg: Message, state: FSMContext):
#     from main import bot
#     from handlers.config import config
#     id_admin = config.chanel_id.get_secret_value()
#     if msg.photo or msg.video:
#         if msg.photo:
#             file_id = msg.photo.file_id
#         elif msg.video:
#             file_id = msg.video.file_id
#         await msg.answer('Изображение получено')
#         await bot.send_document(
#             chat_id=id_admin,
#             document=file_id,
#             caption=f"📄 Документ от пользователя {msg.from_user.full_name}\n"
#         )
#     else:
#         await msg.answer('Пожалуйста отправьте документ или нажмите кнопку отмена')
