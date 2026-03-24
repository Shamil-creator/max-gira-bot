# Gira_MAX Migration Report

## Что сделано

1. Создан новый проект в `/Users/shamilsadykov/Desktop/Gira_MAX` из core-кода исходного бота, без использования папок `MAX` и `MAX2`.
2. Переведен bootstrap на стек `maxapi` + polling:
   - `main.py` переписан под запуск MAX-бота;
   - добавлен startup с инициализацией image cache и scheduler.
3. Убран внешний Redis:
   - добавлен `services/draft_store.py` (Postgres-backed Redis-like интерфейс);
   - глобальный `redis` в `main.py` теперь `PostgresDraftStore`.
4. Добавлен совместимый слой `aiogram -> maxapi` в локальной папке `aiogram/`:
   - поддержаны `Bot`, `Dispatcher`, `Router`, `F`, базовые типы/клавиатуры/FSM;
   - сохранена совместимость существующих обработчиков.
5. Админская маршрутизация переведена на единый чат:
   - удалены `message_thread_id` из `handlers/*`;
   - `handlers/admin_group.py` больше не фильтрует по топику;
   - сообщения в админ-чат маркируются префиксами (`[АДМИН]`, `[ОПЛАТА]`, `[ТЕХЗАЯВКА]`, `[РЕМОНТ]`, `[РАСТОРЖЕНИЕ]`, `[ДОКУМЕНТЫ]`).
6. Добавлены миграции:
   - `migrations/001_create_bot_drafts.sql`;
   - `migrations/002_backup_and_clear_legacy_business_documents.sql`.
7. Обновлены зависимости и окружение:
   - `requirements.txt` без `aiogram` и `redis`;
   - добавлен `.env.example` с `MAX_BOT_TOKEN`.
8. Настроен тестовый контур:
   - `pytest.ini` теперь указывает на `tests/`;
   - добавлены статические тесты миграционных ограничений.

## Важные файлы

- `main.py`
- `handlers/config.py`
- `services/draft_store.py`
- `handlers/admin_chat.py`
- `migrations/001_create_bot_drafts.sql`
- `migrations/002_backup_and_clear_legacy_business_documents.sql`
- `aiogram/*` (совместимый слой)

## Как запускать

1. `cd /Users/shamilsadykov/Desktop/Gira_MAX`
2. `python3 -m venv .venv`
3. `.venv/bin/pip install -r requirements.txt`
4. Заполнить `.env` (или скопировать из `.env.example`).
5. Применить SQL-миграции в Postgres.
6. `.venv/bin/python main.py`

## Замечания

- Для безопасного отказа от legacy Telegram-вложений сначала выполняйте backup-миграцию (`002_*`), затем проверяйте рассылки документов в MAX.
- Сценарии с вложениями зависят от доступности MAX upload API и валидных URL/файлов.
