# Инструкция по полной настройке проекта Gira_MAX на ПК

Этот проект — бот для платформы MAX Messenger, написанный на Python с использованием `maxapi` (скрытого за слоем совместимости с `aiogram`), PostgreSQL для хранения данных и Yandex.Disk для облачного хранения.

## 1. Подготовка системы
* **Python 3.10 или 3.12** (рекомендуется).
* **PostgreSQL 14+** (база данных).
* **Git** (для работы с кодом).
* **Аккаунт на MAX Messenger** (и созданный бот).
* **Yandex.Disk Token** (для работы с файлами).

## 2. Установка PostgreSQL
1. Скачайте и установите PostgreSQL с [официального сайта](https://www.postgresql.org/download/).
2. Создайте базу данных (например, `gira`).
3. Запомните пароль пользователя `postgres`.

## 3. Развёртывание кода
1. Откройте терминал (PowerShell или CMD на Windows).
2. Перейдите в папку проекта:
   ```bash
   cd C:\путь\к\проекту\Gira_MAX
   ```
3. Создайте виртуальное окружение:
   ```bash
   python -m venv .venv
   ```
4. Активируйте его:
   - **Windows:** `.venv\Scripts\activate`
   - **Linux/Mac:** `source .venv/bin/activate`

5. Установите все библиотеки:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## 4. Конфигурация (.env)
Создайте файл `.env` в корневой папке (скопируйте из `.env.example`):
1. **MAX_BOT_TOKEN**: Токен вашего бота.
2. **DB_HOST**: `localhost` (если база на этом же ПК).
3. **DB_PORT**: `5432`.
4. **DB_NAME**: `gira` (имя созданной БД).
5. **DB_USER**: `postgres`.
6. **DB_PASSWORD**: ваш пароль.
7. **CHANEL_ID**: ID чата администраторов (начинается с `-100...`).
8. **CLIENT_ID**: ваш ID клиента (если требуется логикой).
9. **YANDEX_DISK_TOKEN**: Токен от [Яндекс.Полигона](https://yandex.ru/dev/disk/poligon/).

## 5. Запуск и база данных
1. Бот автоматически создаст таблицу `bot_drafts` при первом старте.
2. Если у вас пустая база, убедитесь, что в ней есть остальные необходимые таблицы (`users`, `bussines`, `us_readings`). Обычно они переносятся через дамп базы (`pg_dump`).
3. Примените SQL-миграции из папки `migrations/` вручную через pgAdmin или консоль:
   ```bash
   psql -U postgres -d gira -f migrations/001_create_bot_drafts.sql
   psql -U postgres -d gira -f migrations/002_backup_and_clear_legacy_business_documents.sql
   ```

## 6. Запуск бота
```bash
python main.py
```
Если всё настроено верно, в консоли появится надпись: `MAX bot started`.

---
⚡ **Важно:** Бот использует планировщик задач (APScheduler). Он будет автоматически отправлять уведомления 26-го числа каждого месяца в 14:30. Убедитесь, что время на ПК настроено верно (Europe/Moscow).
