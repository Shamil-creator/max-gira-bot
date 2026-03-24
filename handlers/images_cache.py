import logging
import json
import os
import asyncio
from aiogram import Bot
from aiogram.types import BufferedInputFile
from typing import Optional

logger = logging.getLogger(__name__)
CACHE_FILE = "image_ids.json"

class ImageCache:
    def __init__(self):
        self.water_id: Optional[str] = None
        self.electricity_id: Optional[str] = None
        self._bot: Optional[Bot] = None
        self._upload_chat_id: Optional[int] = None
    
    async def initialize(self, bot: Bot, upload_chat_id: int):
        self._bot = bot
        self._upload_chat_id = upload_chat_id
        
        if not upload_chat_id:
            raise ValueError("Не указан upload_chat_id! Укажите ваш личный Telegram ID")
        
        # 1. Пробуем загрузить из файла
        if await self._load_from_file():
            logger.info("✅ File_id загружены из кэш-файла")
            # Для MAX поддерживаем только URL-ссылки.
            if await self._quick_validate():
                return
            else:
                logger.warning("File_id невалидны для MAX, используем локальные изображения")
                return
        
        # 2. Загружаем заново
        logger.info(f"Загружаю изображения в чат {upload_chat_id}...")
        try:
            await self._upload_and_cleanup()
            # 3. Сохраняем в файл
            await self._save_to_file()
        except Exception as e:
            logger.warning(f"Не удалось подготовить удаленные ссылки изображений, используем локальные файлы: {e}")
    
    async def _upload_and_cleanup(self):
        try:
            # 1. Загружаем воду
            logger.info("Загружаю water.png...")
            with open("images/new_water.png", "rb") as f:
                water_msg = await self._bot.send_photo(
                    chat_id=self._upload_chat_id,
                    photo=BufferedInputFile(f.read(), "new_water.png"),
                    caption="#temp_upload_water"  # Метка для идентификации
                )
                self.water_id = water_msg.photo[-1].file_id
                logger.info(f"✅ Water file_id получен")
            
            # 2. Загружаем электричество
            logger.info("Загружаю electricity.png...")
            with open("images/electricity.png", "rb") as f:
                electricity_msg = await self._bot.send_photo(
                    chat_id=self._upload_chat_id,
                    photo=BufferedInputFile(f.read(), "electricity.png"),
                    caption="#temp_upload_electricity"
                )
                self.electricity_id = electricity_msg.photo[-1].file_id
                logger.info(f"✅ Electricity file_id получен")
            
            # 3. Ждем немного чтобы сообщения отправились
            await asyncio.sleep(0.5)
            
            # 4. Удаляем сообщения чтобы не засорять чат
            logger.info("Удаляю временные сообщения...")
            try:
                await self._bot.delete_message(self._upload_chat_id, water_msg.message_id)
                await self._bot.delete_message(self._upload_chat_id, electricity_msg.message_id)
                logger.info("✅ Временные сообщения удалены")
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщения (можно игнорировать): {e}")
            
            logger.info("✅ Изображения загружены и file_id сохранены")
                
        except FileNotFoundError as e:
            logger.error(f"❌ Файл изображения не найден: {e}")
            logger.error("Убедитесь что файлы есть в папке images/:")
            logger.error("  - images/water.png")
            logger.error("  - images/electricity.png")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки изображений: {e}")
            raise
    
    async def _load_from_file(self) -> bool:
        try:
            if not os.path.exists(CACHE_FILE):
                logger.info("Файл кэша не найден")
                return False
            
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.water_id = data.get("water_id")
            self.electricity_id = data.get("electricity_id")
            
            if self.water_id and self.electricity_id:
                logger.info("File_id загружены из файла")
                return True
            else:
                logger.warning("В файле кэша не все file_id")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка чтения кэш-файла: {e}")
            return False
    
    async def _save_to_file(self):
        try:
            data = {
                "water_id": self.water_id,
                "electricity_id": self.electricity_id,
                "info": "Эти file_id можно использовать для отправки фото без загрузки"
            }
            
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ File_id сохранены в {CACHE_FILE}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша: {e}")
    
    async def _quick_validate(self) -> bool:
        try:
            return self._is_supported_remote_ref(self.water_id) and self._is_supported_remote_ref(self.electricity_id)
        except:
            return False

    @staticmethod
    def _is_supported_remote_ref(value: Optional[str]) -> bool:
        return isinstance(value, str) and value.startswith(("http://", "https://"))
    
    def get_water(self) -> str:
        if self._is_supported_remote_ref(self.water_id):
            return self.water_id
        local_path = "images/new_water.png"
        if os.path.exists(local_path):
            return local_path
        raise ValueError("Water image not available: remote id is invalid and local file is missing.")
    
    def get_electricity(self) -> str:
        if self._is_supported_remote_ref(self.electricity_id):
            return self.electricity_id
        local_path = "images/electricity.png"
        if os.path.exists(local_path):
            return local_path
        raise ValueError("Electricity image not available: remote id is invalid and local file is missing.")
    
    def is_initialized(self) -> bool:
        return self.water_id is not None and self.electricity_id is not None

image_cache = ImageCache()
