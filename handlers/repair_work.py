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
from states.repair_work_states import Repair_State

repair_work_router = Router()

def send_docs_in_rep_work_keyboard():
    buttons = [
        [types.InlineKeyboardButton(text='Отправить', callback_data='send_rw_cb'), types.InlineKeyboardButton(text='Не отправлять', callback_data='dont_send_rw_cb')]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons, resize_keyboard=True)
    return keyboard

@repair_work_router.message(Repair_State.Wait_document_for_termination_State)
async def get_docs(msg: Message, state: FSMContext):
    if msg.document:
        file_id = msg.document.file_id
        await state.update_data(file_id=file_id)
        await msg.answer('Документ получен, вы желаете отправить его?', reply_markup=send_docs_in_rep_work_keyboard())
        
    else:
        await msg.answer('Пожалуйста отправьте документ')

@repair_work_router.callback_query(F.data.in_(['send_rw_cb','dont_send_rw_cb']))
async def callback_query(call: CallbackQuery, state:FSMContext):
    from main import bot
    from handlers.config import config
    id_admin = config.chanel_id.get_secret_value()
    from handlers.run import build_menu_keyboard
    data = call.data
    us_data = await state.get_data()
    file_id = us_data.get('file_id')
    await call.message.delete()
    if data == 'dont_send_rw_cb':
        await state.set_state(Auth_States.menu_state)
        await call.message.answer('Вы в меню', reply_markup=await build_menu_keyboard(call.from_user.id))
    elif data == 'send_rw_cb':
        await bot.send_document(
            chat_id=id_admin,
            document=file_id,
            caption=f"[РЕМОНТ] 📄 Документ от пользователя {call.message.from_user.full_name}\n"
        )
