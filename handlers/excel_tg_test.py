import asyncio
import shutil
import asyncpg
from docx import Document
import pandas as pd
from datetime import datetime
import re
import os
from openpyxl import load_workbook
from dateutil.relativedelta import relativedelta
from handlers.config import config
import math
import tempfile
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
from shutil import copy2
import time
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

async def get_data(query: str, *params):
    try:
        conn = await asyncpg.connect(config.db_connection)
        result = await conn.fetch(query,*params)
        await conn.close()
        return result
    except Exception as e: 
        print(f"Ошибка: {e}")
        return None

async def get_info_business(id):
    us_businesses = await get_data('SELECT toa.name, fodb.name AS fodb_name, b.* FROM users u RIGHT JOIN Bussines b ON b.id = u.id_business JOIN Type_of_Activity toa ON b.id_type_of_activity = toa.id JOIN form_of_doing_business fodb ON fodb.id = b.id_form WHERE u.User_Id = $1', str(id))
    return us_businesses

async def delete_sheet_in_excel(sheet_name):
    try:
        file_path = 'docs/ГИРА_1006теккаа2.xlsx'
        loop = asyncio.get_event_loop()
        wb = await loop.run_in_executor(None, load_workbook, file_path)
        
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Лист '{sheet_name}' не найден")
        
        # Удаляем лист
        wb.remove(wb[sheet_name])
        
        # Сохраняем в отдельном потоке
        await loop.run_in_executor(None, wb.save, file_path)
        
        print(f"Лист '{sheet_name}' успешно удален")
        
    except FileNotFoundError:
        print(f"Файл {file_path} не найден")
    except Exception as e:
        print(f"Ошибка: {e}")

async def get_sheet_name_in_id_business(id_business):
    results = await get_data('SELECT sheet_name FROM bussines WHERE id = $1',id_business)
    if results:
        for list in results:
            sheet_name = list['sheet_name']
    return sheet_name

async def delete_in_excel(name_tenant):
    wb = load_workbook('docs/ГИРА_1006теккаа2.xlsx')
    sheet = wb['Реестр']
    col_arendator = None
    for col in range(1, sheet.max_column + 1):
        if sheet.cell(row=1, column=col).value == "Арендатор":
            col_arendator = col
            break

    if col_arendator:
        search_value = name_tenant
        for row in range(sheet.max_row, 1, -1):
            if sheet.cell(row=row, column=col_arendator).value == search_value:
                sheet.delete_rows(row)
                print(f"Удалена строка {row} на листе 'Реестр'")
                break
        wb.save('docs/ГИРА_1006теккаа2.xlsx')
    else:
        print("Столбец 'Арендатор' не найден на листе 'Реестр'")

async def add_tenant_for_user(id, volume, amount):
    file_path_new = 'docs/ГИРА_1006теккаа2.xlsx'
    print(f'Проверка получаемого id арендатора - {id}')
    print(f'Проверка значения тепла арендатора - {volume}')
    print(f'Проверка суммы в рублях тепла арендатора - {amount}')
    try:
        name_sheet = await get_sheet_name_in_id_business(id)
        df = pd.read_excel(file_path_new, sheet_name=name_sheet)
        wb = load_workbook(file_path_new)
        ws = wb[name_sheet]
        current_date = datetime.now()
        date_month_ago = current_date - relativedelta(months=1)
        this_date_in_first_day_oh_month = datetime(date_month_ago.year, date_month_ago.month, 1)
        found_columns = []
        for col in df.columns:
            if isinstance(col, datetime):
                if col.date() == this_date_in_first_day_oh_month.date():
                    found_columns.append(col)
            elif isinstance(col, str):
                try:
                    col_date = pd.to_datetime(col)
                    if col_date.date() == this_date_in_first_day_oh_month.date():
                        found_columns.append(col)
                except:
                    continue
        for column in found_columns:
            columm_position = df.columns.get_loc(column)
        position_this_indicator_heat_column = columm_position - 2
        position_this_indicator_heat_row = 1
        excel_row_heat = position_this_indicator_heat_row + 8
        excel_col_heat = position_this_indicator_heat_column + 1 
        excel_row_amount_heat = position_this_indicator_heat_row + 8
        excel_col_amount_heat = position_this_indicator_heat_column+3

        ws.cell(row=excel_row_heat,column=excel_col_heat,value=volume)
        ws.cell(row=excel_row_amount_heat,column=excel_col_amount_heat,value=amount)
        wb.save(file_path_new)
    except Exception as e:
        print(f'Возникла ошибка - {e}')

async def safe_add_to_excel(data):
    file_path = 'docs/ГИРА_1006теккаа2.xlsx' 
    target_sheet = 'Реестр'
    
    if not os.path.exists(file_path):
        print(f"❌ Файл {file_path} не найден!")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.replace('.xlsx', f'_backup_{timestamp}.xlsx')
    
    try:
        wb = load_workbook(file_path)
        all_sheets = wb.sheetnames
        print(f"\n📊 Все листы в книге ({len(all_sheets)}):")
        for i, sheet in enumerate(all_sheets, 1):
            print(f"  {i}. '{sheet}'")
            
        # Выбор листа
        if isinstance(target_sheet, int):
            if 1 <= target_sheet <= len(all_sheets):
                sheet_name = all_sheets[target_sheet - 1]
            else:
                print(f"❌ Нет листа с номером {target_sheet}")
                return
        else:
            if target_sheet in all_sheets:
                sheet_name = target_sheet
            else:
                print(f"❌ Лист '{target_sheet}' не найден")
                return
        
        print(f"\n🎯 Целевой лист: '{sheet_name}'")
        
        # Создаем резервную копию
        wb.save(backup_path)
        print(f"💾 Создана резервная копия: {backup_path}")
        
        ws = wb[sheet_name]
        
        # Определяем есть ли заголовки
        has_headers = any(ws.cell(row=1, column=col).value for col in range(1, 10))
        start_row = 2 if has_headers else 1
        
        # Находим первую пустую строку
        row = start_row
        while ws[f'A{row}'].value is not None:
            row += 1
            if row > 1000:  # защита от бесконечного цикла
                print("⚠️ Достигнут лимит в 1000 строк")
                break
        
        print(f"📝 Первая пустая строка: {row}")
        
        # Добавляем данные
        added = 0
        print(f"Заполняю строку {row}:")
            
        # Заполняем основные поля
        ws[f'A{row}'] = data[0]
        ws[f'D{row}'] = data[1] 
        ws[f'E{row}'] = data[2]
        ws[f'F{row}'] = data[3]
        ws[f'G{row}'] = data[4]
        ws[f'H{row}'] = data[5]
        ws[f'I{row}'] = data[6]
        ws[f'K{row}'] = data[7]
        ws[f'R{row}'] = data[8]
        ws[f'S{row}'] = data[9]
        ws[f'T{row}'] = data[10]
        ws[f'V{row}'] = data[11]
        ws[f'N{row}'] = data[12]
        
        added = 1 
        if added > 0:
            wb.save(file_path)
            print(f"\n✅ Добавлено {added} записей на лист '{sheet_name}'")
            print("✅ Остальные листы не изменены")
        else:
            print("\n⚠️ Нет данных для добавления")
        
        wb.close()
        
        # Показываем результат
        print(f"\n📋 Итог:")
        print(f"  - Всего листов в книге: {len(all_sheets)}")
        print(f"  - Измененный лист: '{sheet_name}'")
        print(f"  - Добавлено записей: {added}")
        print(f"  - Резервная копия: {backup_path}")
        
        # Проверка что данные записались
        if added > 0:
            wb_check = load_workbook(file_path)
            ws_check = wb_check[sheet_name]
            print(f"\n🔍 Проверка последней заполненной строки {row-1}:")
            print(f"  A{row-1}: {ws_check[f'A{row-1}'].value}")
            print(f"  B{row-1}: {ws_check[f'B{row-1}'].value}")
            wb_check.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print(f"⚠️ Файл не был сохранен. Используйте резервную копию: {backup_path}")

async def copy_sheet_safe(new_sheet_name):
    file_path = 'docs/ГИРА_1006теккаа2.xlsx'
    source_sheet_name = 'ЛИСТШАБЛОН'
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл {file_path} не найден")
    
    # Создаем резервную копию перед изменениями
    backup_file = file_path.replace('.xlsx', '_backup.xlsx')
    import shutil
    shutil.copy2(file_path, backup_file)
    print(f"✓ Создана резервная копия: {backup_file}")
    
    try:
        # Загружаем книгу с формулами
        wb = load_workbook(file_path, data_only=False)
        
        # Запоминаем все существующие листы
        original_sheets = wb.sheetnames.copy()
        print(f"📊 Листы в книге: {', '.join(original_sheets)}")
        
        # Проверяем исходный лист
        if source_sheet_name not in original_sheets:
            raise ValueError(f"Лист '{source_sheet_name}' не найден")
        
        # Проверяем новое имя
        if new_sheet_name in original_sheets:
            # Автоматически генерируем уникальное имя
            base_name = new_sheet_name
            counter = 1
            while new_sheet_name in wb.sheetnames:
                new_sheet_name = f"{base_name}_{counter}"
                counter += 1
            print(f"⚠ Имя '{base_name}' занято, использую '{new_sheet_name}'")
        
        # Получаем исходный лист
        source_sheet = wb[source_sheet_name]
        
        # Копируем лист
        new_sheet = wb.copy_worksheet(source_sheet)
        new_sheet.title = new_sheet_name
        
        # Проверяем, что другие листы не изменились
        print("\n🔍 Проверка сохранности других листов:")
        for sheet_name in original_sheets:
            if sheet_name != source_sheet_name:
                sheet = wb[sheet_name]
                # Проверяем первые несколько ячеек для демонстрации
                a1_value = sheet['A1'].value if sheet['A1'].value else "пусто"
                print(f"  • {sheet_name}: A1 = {a1_value}")
        
        # Сохраняем
        wb.save(file_path)
        
        print(f"\n✅ Лист '{source_sheet_name}' успешно скопирован как '{new_sheet_name}'")
        print(f"📋 Всего листов в книге: {len(wb.sheetnames)}")
        
        # Проверяем формулы на новом листе
        check_formulas(new_sheet)
        
        return True
        
    except Exception as e:
        # Восстанавливаем из резервной копии в случае ошибки
        print(f"❌ Ошибка: {e}")
        shutil.copy2(backup_file, file_path)
        print("🔄 Восстановлено из резервной копии")
        return False

def check_formulas(sheet):
    """Проверяет наличие формул на листе"""
    formulas = []
    for row in sheet.iter_rows(max_row=10, max_col=5):  # Проверяем первые 10 строк и 5 колонок
        for cell in row:
            if cell.data_type == 'f':
                formulas.append(f"{cell.coordinate}: {cell.value}")
    
    if formulas:
        print("\n📝 Найденные формулы на новом листе (первые 5):")
        for f in formulas[:5]:
            print(f"  {f}")
    else:
        print("\n📝 Формул на видимой области не найдено (это нормально)")

async def get_volume_and_amount_month(id_us):
    from handlers.meter_readings import get_sheet_name
    records_list = await get_info_business(id_us)
    if records_list:
        for list in records_list:
            square = list['square']
    name_sheet = await get_sheet_name(id_us)
    file_path = 'docs/ГИРА_1006теккаа2.xlsx'

     # ======== XLWINGS ДЛЯ ВЫЧИСЛЕНИЯ ФОРМУЛ ========
    try:
        import xlwings
        from openpyxl import load_workbook
        
        print("🔥 ВЫЧИСЛЯЮ ФОРМУЛЫ ЧЕРЕЗ XLWINGS...")
        
        excel_app = xlwings.App(visible=False)
        excel_book = excel_app.books.open(os.path.abspath(file_path))
        excel_book.save()
        excel_book.close()
        excel_app.quit()
        
        print("✅ ФОРМУЛЫ ВЫЧИСЛЕНЫ!")
        
    except Exception as e:
        print(f"⚠️ Xlwings не сработал: {e}")

    
    df = pd.read_excel(file_path, sheet_name=name_sheet,engine='openpyxl')
    current_date = datetime.now()
    date_month_ago = current_date - relativedelta(months=1)
    date_two_month_ago = current_date - relativedelta(months=2)
    start_date = datetime(current_date.year, current_date.month, 1)
    end_date = datetime(date_month_ago.year, date_month_ago.month, 1)
    print(f'Время старта{start_date}')
    print(f'Время завершения{end_date}')
    found_columns = []
    for col in df.columns:
        col_date = None
        
        # Получаем дату из колонки
        if isinstance(col, datetime):
            col_date = col
        # elif isinstance(col, str):
        #     try:
        #         col_date = pd.to_datetime(col, dayfirst=True)
        #     except:
        #         continue
        
        if col_date:
            if col_date.date() == start_date.date():
                index = df.columns.get_loc(col)
                found_columns.append(index)
            elif col_date.date() == end_date.date():
                index = df.columns.get_loc(col)
                found_columns.append(index)
    start_index = found_columns[0]
    end_index = found_columns[1]
    new_found_columns = []
    while start_index != end_index+3:
        new_found_columns.append(start_index)
        start_index+=1
        print(start_index)
    data_in_columns = df.iloc[:,new_found_columns].values.tolist()
    print(f'Проверка на забранные таблицы из таблицы {data_in_columns}')
    list_needed_data = []
    row_index = 0
    for row_data in data_in_columns:
        if row_index == 0:
            pass
        elif row_index % 2 == 0:
            list_needed_data.append(row_data[5])
        else:
            row_data.pop(2)
            row_data.pop(1)
            list_needed_data.append(row_data)
        row_index+=1
    print(f'Полученные нужные показатели {list_needed_data}')
    final_row_index = 1
    final_count_row = 0
    final_list = []
    for final_data in list_needed_data:
        print(f'отслеживаем данные, которые нужны {final_data}')
        if final_count_row <= 5:
            if final_row_index == 2:
                current_value = final_data
                final_list[-1].append(current_value)
                final_row_index = 1
            else: 
                final_list.append(final_data)
                final_row_index+=1
            final_count_row+=1
        else:
            if final_row_index == 2:
                current_value = final_data
                final_list[-1].append(final_data)
                final_row_index = 1
            else: 
                short_list = [final_data[3]]
                final_list.append(short_list)
                final_row_index+=1  
        # final_list.append(final_data)
    final_count_row_new = 0
    services_dict = {
    '⚡️ Электроэнергия': ['• Показатели за предыдущий месяц:', '• Показатели за текущий месяц:', '• Разница:','• Ставка:', '• Сумма к оплате:'],
    '🚰 Холодная вода': ['• Показатели за предыдущий месяц:', '• Показатели за текущий месяц:', '• Разница:','• Ставка:', '• Сумма к оплате:'],
    '🔥 Горячая вода': ['• Показатели за предыдущий месяц:', '• Показатели за текущий месяц:', '• Разница:','• Ставка:', '• Сумма к оплате:'],
    '🌡 Отопление': ['• Ставка:', '• Площадь:', '• Сумма:'],
    '🏢 Эксплуатационные услуги': ['• Сумма:']
    }
    print(f'Итоговые данные, после преобразований\n{final_list}')
    text = f'📍Счёт за прошлый месяц\n\n'
    sum = 0
    for readings in final_list:
        if final_count_row_new == 0:
            electricity_template = services_dict['⚡️ Электроэнергия']
            text+= f'⚡️ Электроэнергия\n{electricity_template[0]} {readings[0]}\n{electricity_template[1]} {readings[1]}\n{electricity_template[2]} {readings[2]}\n{electricity_template[3]} {readings[4]:.2f}\n{electricity_template[4]} {readings[3]:.2f}\n\n'
            sum+=float(readings[3])
        elif final_count_row_new == 1:
            cold_water_template = services_dict['🚰 Холодная вода']
            text+= f'🚰 Холодная вода\n{cold_water_template[0]} {readings[0]}\n{cold_water_template[1]} {readings[1]}\n{cold_water_template[2]} {readings[2]}\n{cold_water_template[3]} {readings[4]:.2f}\n{cold_water_template[4]} {readings[3]:.2f}\n\n'
            sum+=float(readings[3])        
        elif final_count_row_new == 2:
            hot_water_template = services_dict['🔥 Горячая вода']
            text+= f'🔥 Горячая вода\n{hot_water_template[0]} {readings[0]}\n{hot_water_template[1]} {readings[1]}\n{hot_water_template[2]} {readings[2]}\n{hot_water_template[3]} {readings[4]:.2f}\n{hot_water_template[4]} {readings[3]:.2f}\n\n'
            sum+=float(readings[3])
        elif final_count_row_new == 3:
            heating_template = services_dict['🌡 Отопление']
            a = readings
            text+= f'🌡 Отопление\n{heating_template[0]} {a[1]:.2f}\n{heating_template[1]} {square}\n{heating_template[2]} {a[0]:.2f}\n\n'
            sum+=float(a[0])
        elif final_count_row_new == 4:
            expluatance_template = services_dict['🏢 Эксплуатационные услуги']
            text+= f'🏢 Эксплуатационные услуги\n{expluatance_template[0]} {readings[0]:.2f}\n'
            sum+=float(readings[0])
        final_count_row_new+=1
    text+=f'\n\n---------------\nИтого: {sum:.2f}'

    return text 

async def save_mr_result_in_excel(name_sheet,us_readings, type_id):
    file_path_new = 'docs/ГИРА_1006теккаа2.xlsx'
    df = pd.read_excel(file_path_new, sheet_name=name_sheet)
    current_date = datetime.now()
    this_date_in_first_day_oh_month = datetime(current_date.year, current_date.month, 1)
    wb = load_workbook(file_path_new)
    ws = wb[name_sheet]
    found_columns = []
    for col in df.columns:
        if isinstance(col, datetime):
            if col.date() == this_date_in_first_day_oh_month.date():
                found_columns.append(col)
        elif isinstance(col, str):
            try:
                col_date = pd.to_datetime(col)
                if col_date.date() == this_date_in_first_day_oh_month.date():
                    found_columns.append(col)
            except:
                continue
    if type_id == 1:
        for column in found_columns:
            columm_position = df.columns.get_loc(column)
        position_this_indicator_cold_water_column = columm_position - 5
        position_this_indicator_cold_water_row = 1
        position_previous_indicator_cold_water_column = columm_position - 2
        position_previous_indicator_cold_water_row = 1
        this_indicator_water = df.iloc[position_this_indicator_cold_water_row, position_this_indicator_cold_water_column]
        previous_indicator_water = df.iloc[position_previous_indicator_cold_water_row, position_previous_indicator_cold_water_column]
        excel_row_cold_water = position_this_indicator_cold_water_row + 4
        excel_col_cold_water = position_this_indicator_cold_water_column + 1  
        ws.cell(row=excel_row_cold_water,column=excel_col_cold_water,value=us_readings)
    elif type_id == 2:
        for column in found_columns:
            columm_position = df.columns.get_loc(column)
        position_this_indicator_electricity_column = columm_position - 5
        position_this_indicator_electricity_row = 1
        position_previous_indicator_electricity_column = columm_position - 2
        position_previous_indicator_electricity_row = 1
        this_indicator_electricity = df.iloc[position_this_indicator_electricity_row, position_this_indicator_electricity_column]
        previous_indicator_electricity = df.iloc[position_previous_indicator_electricity_row, position_previous_indicator_electricity_column]
        excel_row_electricity = position_this_indicator_electricity_row + 2 
        excel_col_electricity = position_this_indicator_electricity_column + 1 
        ws.cell(row=excel_row_electricity, column=excel_col_electricity, value=us_readings)
    elif type_id == 3:
        for column in found_columns:
            columm_position = df.columns.get_loc(column)
        position_this_indicator_hot_water_column = columm_position - 5
        position_this_indicator_hot_water_row = 1
        position_previous_indicator_hot_water_column = columm_position - 2
        position_previous_indicator_hot_water_row = 1
        this_indicator_water = df.iloc[position_this_indicator_hot_water_row, position_this_indicator_hot_water_column]
        previous_indicator_water = df.iloc[position_previous_indicator_hot_water_row, position_previous_indicator_hot_water_column]
        excel_row_hot_water = position_this_indicator_hot_water_row + 6
        excel_col_hot_water = position_this_indicator_hot_water_column + 1 
        ws.cell(row=excel_row_hot_water, column=excel_col_hot_water, value=us_readings) 
    wb.save(file_path_new)

async def count_tenant_excel():
    file_path = 'docs/ГИРА_1006теккаа2.xlsx'
    # Читаем лист "Реестр"
    df = pd.read_excel(file_path, sheet_name='Реестр')

    # Считаем количество записей в столбце "Арендатор"
    count = df['Арендатор'].count()
    return count

async def create_excel(all_indicators,id_us,count_users):
     # ======== ПОЛУЧАЕМ ДАННЫЕ ИЗ ВАШЕГО КОДА ========
    from handlers.meter_readings import get_sheet_name
    
    # Получаем площадь
    records_list = await get_info_business(id_us)
    square = 0
    if records_list:
        for record in records_list:
            square = record['square']
    
    # Получаем имя листа
    name_sheet = await get_sheet_name(id_us)
    file_path = 'docs/ГИРА_1006теккаа2.xlsx'
    
    # ======== XLWINGS ДЛЯ ВЫЧИСЛЕНИЯ ФОРМУЛ ========
    try:
        import xlwings
        print("🔥 ВЫЧИСЛЯЮ ФОРМУЛЫ ЧЕРЕЗ XLWINGS...")
        
        excel_app = xlwings.App(visible=False)
        excel_book = excel_app.books.open(os.path.abspath(file_path))
        excel_book.save()
        excel_book.close()
        excel_app.quit()
        print("✅ ФОРМУЛЫ ВЫЧИСЛЕНЫ!")
    except Exception as e:
        print(f"⚠️ Xlwings не сработал: {e}")
    
    # ======== ЧИТАЕМ ДАННЫЕ ИЗ EXCEL ========
    df = pd.read_excel(file_path, sheet_name=name_sheet, engine='openpyxl')
    
    # Вычисляем даты
    current_date = datetime.now()
    date_month_ago = current_date - relativedelta(months=1)
    date_two_month_ago = current_date - relativedelta(months=2)
    start_date = datetime(current_date.year, current_date.month, 1)
    end_date = datetime(date_month_ago.year, date_month_ago.month, 1)
    
    print(f'Время старта: {start_date}')
    print(f'Время завершения: {end_date}')
    
    # Находим нужные колонки по датам
    found_columns = []
    for col in df.columns:
        col_date = None
        
        if isinstance(col, datetime):
            col_date = col
        
        if col_date:
            if col_date.date() == start_date.date():
                index = df.columns.get_loc(col)
                found_columns.append(index)
            elif col_date.date() == end_date.date():
                index = df.columns.get_loc(col)
                found_columns.append(index)
    
    if len(found_columns) < 2:
        print("❌ Не найдены нужные колонки с датами")
        return None
    
    start_index = found_columns[0]
    end_index = found_columns[1]
    
    # Получаем диапазон колонок
    new_found_columns = []
    while start_index != end_index + 3:
        new_found_columns.append(start_index)
        start_index += 1
    
    # Получаем данные из нужных колонок
    data_in_columns = df.iloc[:, new_found_columns].values.tolist()
    print(f'Проверка на забранные таблицы из таблицы {data_in_columns}')
    
    # Формируем list_needed_data
    list_needed_data = []
    row_index = 0
    for row_data in data_in_columns:
        if row_index == 0:
            pass
        elif row_index % 2 == 0:
            list_needed_data.append(row_data[5])
        else:
            row_data.pop(2)
            row_data.pop(1)
            list_needed_data.append(row_data)
        row_index += 1
    
    print(f'Полученные нужные показатели {list_needed_data}')
    
    # Формируем final_list
    final_row_index = 1
    final_count_row = 0
    final_list = []
    
    for final_data in list_needed_data:
        print(f'отслеживаем данные, которые нужны {final_data}')
        if final_count_row <= 5:
            if final_row_index == 2:
                current_value = final_data
                final_list[-1].append(current_value)
                final_row_index = 1
            else: 
                final_list.append(final_data)
                final_row_index += 1
            final_count_row += 1
        else:
            if final_row_index == 2:
                current_value = final_data
                final_list[-1].append(current_value)
                final_row_index = 1
            else:
                # Проверяем, является ли final_data списком с nan
                if isinstance(final_data, list) and any(isinstance(x, float) and math.isnan(x) for x in final_data if isinstance(x, float)):
                    # Берем оба нужных значения сразу: [индекс1, индекс3]
                    short_list = [final_data[1], final_data[3]]  # [1234, 12]
                else:
                    short_list = [final_data[3]]  # оригинальная логика
                    
                final_list.append(short_list)
                final_row_index += 1
    
    print(f"✅ final_list получен: {final_list}")
    print(f'{all_indicators}')
    # ======== СОЗДАЕМ ВРЕМЕННЫЙ EXCEL ФАЙЛ ========
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_file = os.path.join(temp_dir, f'report_{id_us}_{timestamp}.xlsx')
    
    # Создаем рабочую книгу
    wb = Workbook()
    
    # ======== СТИЛИ ========
    header_font = Font(bold=True, size=12)
    center_alignment = Alignment(horizontal='center', vertical='center')
    left_alignment = Alignment(horizontal='left', vertical='center')
    right_alignment = Alignment(horizontal='right', vertical='center')
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    header_fill = PatternFill(start_color='E6E6E6', end_color='E6E6E6', fill_type='solid')
    total_fill = PatternFill(start_color='FFFF99', end_color='FFFF99', fill_type='solid')
    
    # ======== ЛИСТ 1: ПОКАЗАТЕЛИ АДМИНА ========
    ws_admin = wb.active
    ws_admin.title = "Показатели ГИРА"
    
    # Заголовки для админа
    headers = ['Показатель', 'Объем', 'Сумма (руб.)']
    for col, header in enumerate(headers, 1):
        cell = ws_admin.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.alignment = center_alignment
        cell.border = thin_border
        cell.fill = header_fill
    
    # Данные админа
    admin_data = [
        ('⚡️ Электроэнергия', 
         all_indicators.get('electro', {}).get('volume', 0),
         all_indicators.get('electro', {}).get('amount', 0)),
        ('🏢 Экспл. услуги',
         '—',
         all_indicators.get('expl', {}).get('amount', 0)),
        ('💧 Водоотведение',
         '—',
         all_indicators.get('drainage', {}).get('amount', 0))
    ]

    count_users = int(count_users)
    expl_amount = float(all_indicators['expl']['amount'])
    price_for_user = expl_amount/count_users



    electro_amount = all_indicators['electro']['amount']
    water_cold_amount = all_indicators['water_cold']['amount']
    water_hot_amount = all_indicators['water_hot']['amount']
    drainage_amount = all_indicators['drainage']['amount']
    full_sum_amount = float(electro_amount)+float(water_cold_amount)+float(water_hot_amount)+float(expl_amount)+float(drainage_amount)
    for row, (name, volume, amount) in enumerate(admin_data, 2):
        cell = ws_admin.cell(row=row, column=1, value=name)
        cell.font = Font(bold=True)
        cell.alignment = left_alignment
        cell.border = thin_border
        
        cell = ws_admin.cell(row=row, column=2, value=volume)
        cell.alignment = center_alignment
        cell.border = thin_border
        if volume == '—':
            cell.value = '—'
        else:
            cell.number_format = '#,##0.00'
        
        cell = ws_admin.cell(row=row, column=3, value=float(amount) if amount != '—' else 0)
        cell.number_format = '#,##0.00'
        cell.alignment = center_alignment
        cell.border = thin_border
    
    # Итог для админа
    total_row = len(admin_data) + 2
    cell = ws_admin.cell(row=total_row, column=2, value="ИТОГО:")
    cell = ws_admin.cell(row=total_row, column=3, value=full_sum_amount)
    cell.font = Font(bold=True)
    cell.alignment = right_alignment
    cell.border = thin_border
    
    cell = ws_admin.cell(row=total_row, column=3, value=f"=SUM(C2:C{total_row-1})")
    cell.font = Font(bold=True)
    cell.number_format = '#,##0.00'
    cell.alignment = center_alignment
    cell.border = thin_border
    cell.fill = total_fill
    
    # ======== ЛИСТ 2: ПОКАЗАТЕЛИ ПОЛЬЗОВАТЕЛЯ ========
    ws_user = wb.create_sheet("Показатели пользователя")
    
    # Заголовки для пользователя
    user_headers = ['Услуга', 'Предыдущий', 'Текущий', 'Разница', 'Тариф', 'Сумма']
    for col, header in enumerate(user_headers, 1):
        cell = ws_user.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.alignment = center_alignment
        cell.border = thin_border
        cell.fill = header_fill
    sum_drainage = float(final_list[1][1]) + float(final_list[2][1])
    service_names = [
    ('⚡️ Электроэнергия', final_list[0] if len(final_list) > 0 else []),
    ('🚰 Холодная вода', final_list[1] if len(final_list) > 1 else []),
    ('🔥 Горячая вода', final_list[2] if len(final_list) > 2 else []),
    ('🌡 Отопление', final_list[3] if len(final_list) > 3 else []),
    ('🏢 Экспл. услуги', final_list[4] if len(final_list) > 4 else []),
    ('💧 Водоотведение', sum_drainage)
]

    row = 2
    formulas_row_start = row
    for service_name, data in service_names:
        if not data:
            continue
        
        cell = ws_user.cell(row=row, column=1, value=service_name)
        cell.font = Font(bold=True)
        cell.alignment = left_alignment
        cell.border = thin_border
        
        if service_name == '🌡 Отопление':
            if len(data) >= 2:
                sum = (data[0]) * float(data[1])
                ws_user.cell(row=row, column=2, value="—")
                ws_user.cell(row=row, column=3, value=data[0])
                ws_user.cell(row=row, column=4, value="—")
                ws_user.cell(row=row, column=5, value=data[1])
                ws_user.cell(row=row, column=6, value=f"=C{row}*E{row}")
                
        elif service_name == '🏢 Экспл. услуги' or service_name == '💧 Водоотведение':
            if service_name == '💧 Водоотведение':
                    # Для водоотведения - вставляем сумму в текущий показатель
                    drainage_amount = all_indicators['drainage']['amount']
                    sum_drainage = float(final_list[1][2]) + float(final_list[2][2])
                    final_drainage_amount = sum_drainage*float(drainage_amount)
                    ws_user.cell(row=row, column=3, value=sum_drainage)
                    ws_user.cell(row=row, column=5, value=drainage_amount)  # Текущий
                    ws_user.cell(row=row, column=6, value=final_drainage_amount)  # Сумма
            elif len(data) >= 1:
                # Для эксплуатации - как обычно
                ws_user.cell(row=row, column=6, value=price_for_user)  # Сумма
                ws_user.cell(row=row, column=2, value='—')  # Предыдущий
                ws_user.cell(row=row, column=3, value='—')  # Текущий
                ws_user.cell(row=row, column=4, value='—')  # Разница
                ws_user.cell(row=row, column=5, value='—')  # Тариф
        else:
            if len(data) >= 4:
                ws_user.cell(row=row, column=2, value=data[0])
                ws_user.cell(row=row, column=3, value=data[1])
                ws_user.cell(row=row, column=4, value=data[2])
                
                if len(data) >= 5:
                    ws_user.cell(row=row, column=5, value=data[4])
                    ws_user.cell(row=row, column=6, value=data[3])
                else:
                    ws_user.cell(row=row, column=5, value=data[2])
        
        # Форматирование
        for col in range(2, 7):
            cell = ws_user.cell(row=row, column=col)
            if cell.value != '—' and cell.value is not None and not str(cell.value).startswith('='):
                try:
                    float(cell.value)
                    cell.number_format = '#,##0.00'
                except:
                    pass
            cell.alignment = center_alignment
            cell.border = thin_border
        
        row += 1
    
    # Итог для пользователя
    total_row = row
    cell = ws_user.cell(row=total_row, column=5, value="ИТОГО К ОПЛАТЕ:")
    cell.font = Font(bold=True)
    cell.alignment = right_alignment
    cell.border = thin_border
    
    if row > formulas_row_start:
        cell = ws_user.cell(row=total_row, column=6, value=f"=SUM(F{formulas_row_start}:F{total_row-1})")
        cell.font = Font(bold=True)
        cell.number_format = '#,##0.00'
        cell.alignment = center_alignment
        cell.border = thin_border
        cell.fill = total_fill
    
    # Настройка ширины колонок
    column_widths = [30, 15, 15, 15, 15, 15, 15]
    for i, width in enumerate(column_widths, 1):
        ws_user.column_dimensions[get_column_letter(i)].width = width
    
    ws_admin.column_dimensions['A'].width = 30
    ws_admin.column_dimensions['B'].width = 15
    ws_admin.column_dimensions['C'].width = 15
    
    # Сохраняем файл
    wb.save(temp_file)
    wb.close()
    
    # Вычисляем формулы через xlwings
    try:
        import xlwings
        print("🔥 ВЫЧИСЛЯЮ ФОРМУЛЫ В ФИНАЛЬНОМ ФАЙЛЕ...")
        
        excel_app = xlwings.App(visible=False)
        excel_book = excel_app.books.open(os.path.abspath(temp_file))
        excel_book.api.Calculate()
        excel_book.save()
        excel_book.close()
        excel_app.quit()
        
        print("✅ ФОРМУЛЫ ВЫЧИСЛЕНЫ!")
    except Exception as e:
        print(f"⚠️ Xlwings не сработал: {e}")
    
    print(f"✅ Временный файл создан: {temp_file}")
    return temp_file


def cleanup_temp_file(file_path: str):
    """Удаляет временный файл"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"✅ Временный файл удален: {file_path}")
    except Exception as e:
        print(f"❌ Ошибка при удалении файла: {e}")

async def admin_indicators(all_indicators):
    file_path_new = 'docs/ГИРА_1006теккаа2.xlsx'
    # file_path_new = 'docs/ГИРА_1006тест.xlsx'
    name_sheet = str('0. ГИРА')
    df = pd.read_excel(file_path_new, sheet_name=name_sheet)
    current_date = datetime.now()
    date_month_ago = current_date - relativedelta(months=1)
    print(date_month_ago)
    print(all_indicators)
    electro_volume = all_indicators['electro']['volume']
    electro_amount = all_indicators['electro']['amount']
    
    cold_and_hot_water_tariff = all_indicators['water_cold']['tariff']


    # heat_volume = all_indicators['heat']['volume']
    # heat_amount = all_indicators['heat']['amount']
    expl_amount = all_indicators['expl']['amount']
    this_date_in_first_day_oh_month = datetime(date_month_ago.year, date_month_ago.month, 1)
    wb = load_workbook(file_path_new)
    ws = wb[name_sheet]
    found_columns = []
    for col in df.columns:
        if isinstance(col, datetime):
            if col.date() == this_date_in_first_day_oh_month.date():
                found_columns.append(col)
        elif isinstance(col, str):
            try:
                col_date = pd.to_datetime(col)
                if col_date.date() == this_date_in_first_day_oh_month.date():
                    found_columns.append(col)
            except:
                continue
    for column in found_columns:
        columm_position = df.columns.get_loc(column)

    position_this_indicator_cold_water_column = columm_position
    position_this_indicator_cold_water_row = 1
    # excel_row_cold_water = position_this_indicator_cold_water_row + 4
    # excel_col_cold_water = position_this_indicator_cold_water_column + 1  
    excel_row_amount_cold_water = position_this_indicator_cold_water_row + 5
    excel_col_amount_cold_water = position_this_indicator_cold_water_column+1

    position_this_indicator_electricity_column = columm_position - 2
    position_this_indicator_electricity_row = 1
    excel_row_electricity = position_this_indicator_electricity_row + 2 
    excel_col_electricity = position_this_indicator_electricity_column + 1 
    excel_row_amount_electricity = position_this_indicator_electricity_row + 2 
    excel_col_amount_electricity = position_this_indicator_electricity_column+3

    position_this_indicator_hot_water_column = columm_position
    position_this_indicator_hot_water_row = 1
    excel_row_hot_water = position_this_indicator_hot_water_row + 6
    excel_col_hot_water = position_this_indicator_hot_water_column + 1 
    excel_row_amount_hot_water = position_this_indicator_hot_water_row + 7
    excel_col_amount_hot_water = position_this_indicator_hot_water_column+1

    # position_this_indicator_heat_column = columm_position - 2
    # position_this_indicator_heat_row = 1
    # excel_row_heat = position_this_indicator_heat_row + 8
    # excel_col_heat = position_this_indicator_heat_column + 1 
    # excel_row_amount_heat = position_this_indicator_heat_row + 8
    # excel_col_amount_heat = position_this_indicator_heat_column+3

    position_this_indicator_expl_column = columm_position - 2
    position_this_indicator_expl_row = 1
    excel_row_amount_expl = position_this_indicator_expl_row + 10
    excel_col_amount_expl = position_this_indicator_expl_column+3
    
    # ws.cell(row=excel_row_hot_water, column=excel_col_hot_water, value=water_hot_volume) 
    ws.cell(row=excel_row_amount_hot_water, column=excel_col_amount_hot_water, value=cold_and_hot_water_tariff) 

    ws.cell(row=excel_row_electricity, column=excel_col_electricity, value=electro_volume)
    ws.cell(row=excel_row_amount_electricity, column=excel_col_amount_electricity, value=electro_amount) 

    # ws.cell(row=excel_row_cold_water,column=excel_col_cold_water,value=water_cold_volume)
    ws.cell(row=excel_row_amount_cold_water,column=excel_col_amount_cold_water,value=cold_and_hot_water_tariff)

    # ws.cell(row=excel_row_heat,column=excel_col_heat,value=heat_volume)
    # ws.cell(row=excel_row_amount_heat,column=excel_col_amount_heat,value=heat_amount)

    ws.cell(row=excel_row_amount_expl,column=excel_col_amount_expl,value=expl_amount)
    wb.save(file_path_new)
    wb.close()

    time.sleep(0.5)

def add_borders_to_table(table):
    tbl = table._element
    tbl_pr = tbl.xpath('w:tblPr')[0] if tbl.xpath('w:tblPr') else None
    
    if not tbl_pr:
        tbl_pr = OxmlElement('w:tblPr')
        tbl.insert(0, tbl_pr)
    
    # Создаем границы
    borders = OxmlElement('w:tblBorders')
    
    for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'single')
        border.set(qn('w:sz'), '4')
        border.set(qn('w:space'), '0')
        border.set(qn('w:color'), 'auto')
        borders.append(border)
    
    tbl_pr.append(borders)

# async def create_word(all_indicators,id_us,count_users,all_information,unexpected_expenses):
#     from handlers.meter_readings import get_sheet_name
    
#     print(all_information)
    
#     try:
#         count_users = int(count_users)
#         expl_amount = float(all_indicators['expl']['amount'])
#         price_for_user = round((expl_amount / count_users),2)
#         records_list = await get_info_business(id_us)
#         square = 0
        
#         if records_list:
#             for record in records_list:
#                 square = record['square']
#                 surname = record['surname']
#                 first_name = record['first_name']
#                 patronymic = record['patronymic']
#                 name_company = record['name_company']
#                 fodb_name = record['fodb_name']

#         short_sfp = f'{surname} {first_name[0]}.{patronymic[0]}.'
#         full_sfp = f'{fodb_name} {name_company}'
        
#         # Получаем имя листа
#         name_sheet = await get_sheet_name(id_us)
#         file_path = 'doc/ГИРА_1006теккаа2.xlsx'
        
#         # ======== XLWINGS ДЛЯ ВЫЧИСЛЕНИЯ ФОРМУЛ ========
#         try:
#             import xlwings
#             print("🔥 ВЫЧИСЛЯЮ ФОРМУЛЫ ЧЕРЕЗ XLWINGS...")
            
#             excel_app = xlwings.App(visible=False)
#             excel_book = excel_app.books.open(os.path.abspath(file_path))
#             excel_book.save()
#             excel_book.close()
#             excel_app.quit()
#             print("✅ ФОРМУЛЫ ВЫЧИСЛЕНЫ!")
#         except Exception as e:
#             print(f"⚠️ Xlwings не сработал: {e}")
        
#         # ======== ЧИТАЕМ ДАННЫЕ ИЗ EXCEL ========
#         df = pd.read_excel(file_path, sheet_name=name_sheet, engine='openpyxl')
#         df = df.fillna(0)
        
#         # Вычисляем даты
#         current_date = datetime.now()
#         date_month_ago = current_date - relativedelta(months=1)
#         date_two_month_ago = current_date - relativedelta(months=2)
#         start_date = datetime(current_date.year, current_date.month, 1)
#         end_date = datetime(date_month_ago.year, date_month_ago.month, 1)
        
#         print(f'Время старта: {start_date}')
#         print(f'Время завершения: {end_date}')
        
#         # Находим нужные колонки по датам
#         found_columns = []
#         for col in df.columns:
#             col_date = None
            
#             if isinstance(col, datetime):
#                 col_date = col
            
#             if col_date:
#                 if col_date.date() == start_date.date():
#                     index = df.columns.get_loc(col)
#                     found_columns.append(index)
#                 elif col_date.date() == end_date.date():
#                     index = df.columns.get_loc(col)
#                     found_columns.append(index)
        
#         if len(found_columns) < 2:
#             print("❌ Не найдены нужные колонки с датами")
#             return None
        
#         start_index = found_columns[0]
#         end_index = found_columns[1]
        
#         # Получаем диапазон колонок
#         new_found_columns = []
#         while start_index != end_index + 3:
#             new_found_columns.append(start_index)
#             start_index += 1
        
#         # Получаем данные из нужных колонок
#         data_in_columns = df.iloc[:, new_found_columns].values.tolist()
#         print(f'Проверка на забранные таблицы из таблицы {data_in_columns}')
        
#         # Формируем list_needed_data
#         list_needed_data = []
#         row_index = 0
#         for row_data in data_in_columns:
#             if row_index == 0:
#                 pass
#             elif row_index % 2 == 0:
#                 list_needed_data.append(row_data[5])
#             else:
#                 row_data.pop(2)
#                 row_data.pop(1)
#                 list_needed_data.append(row_data)
#             row_index += 1
        
#         print(f'Полученные нужные показатели {list_needed_data}')
        
#         # Формируем final_list
#         final_row_index = 1
#         final_count_row = 0
#         final_list = []
        
#         for final_data in list_needed_data:
#             print(f'отслеживаем данные, которые нужны {final_data}')
#             if final_count_row <= 5:
#                 if final_row_index == 2:
#                     current_value = final_data
#                     final_list[-1].append(current_value)
#                     final_row_index = 1
#                 else: 
#                     final_list.append(final_data)
#                     final_row_index += 1
#                 final_count_row += 1
#             else:
#                 if final_row_index == 2:
#                     current_value = final_data
#                     final_list[-1].append(current_value)
#                     final_row_index = 1
#                 else:
#                     # Проверяем, является ли final_data списком с nan
#                     if isinstance(final_data, list) and any(isinstance(x, float) and math.isnan(x) for x in final_data if isinstance(x, float)):
#                         # Берем оба нужных значения сразу: [индекс1, индекс3]
#                         short_list = [final_data[1], final_data[3]]  # [1234, 12]
#                     else:
#                         short_list = [final_data[3]]  # оригинальная логика
                        
#                     final_list.append(short_list)
#                     final_row_index += 1
            
#         # Расчеты для водоотведения и отопления
#         drainage_amount = all_indicators['drainage']['amount']
#         sum_drainage = float(final_list[1][2]) + float(final_list[2][2])
#         final_drainage_amount = round(sum_drainage * float(drainage_amount),2)
#         heat_sum = round(float(final_list[3][1]) * float(final_list[3][0]), 2)
        
#         # ======== РАБОТА С WORD ========
#         # Путь к шаблону
#         template_path = "docs/Акт_расчета.docx"
    
#         # Создаем временный файл
#         with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
#             temp_path = tmp.name
        
#         # Копируем шаблон во временный файл
#         copy2(template_path, temp_path)
        
#         # Открываем документ
#         doc = Document(temp_path)
        
#         for table in doc.tables:
#             for row in table.rows:
#                 for cell in row.cells:
#                     for paragraph in cell.paragraphs:
#                         if 'thisday' in paragraph.text.lower():  # регистронезависимый поиск
#                             # Заменяем с учетом возможного регистра
#                             new_text = paragraph.text.replace('thisday', str(all_information[0]))
#                             new_text = new_text.replace('Thisday', str(all_information[0]))
#                             new_text = new_text.replace('THISDAY', str(all_information[0]))
#                             paragraph.text = new_text
#                             print(f"Заменено в таблице: {new_text}")
#         # --- ТЕКСТОВЫЕ ЗАМЕНЫ (как у тебя работает) ---
#         for paragraph in doc.paragraphs:
#             if 'tenant_sfp' in paragraph.text:
#                 paragraph.text = paragraph.text.replace('tenant_sfp', full_sfp)
#             if 'start_day' in paragraph.text:
#                 paragraph.text = paragraph.text.replace('start_day', str(all_information[1]))
#             if 'end_day' in paragraph.text:
#                 paragraph.text = paragraph.text.replace('end_day', str(all_information[2]))
#             if 'monthyear' in paragraph.text:
#                 paragraph.text = paragraph.text.replace('monthyear', str(all_information[3]))
#             if 'square' in paragraph.text:
#                 paragraph.text = paragraph.text.replace('square', str(square))
#             if 'tenantshortsfp' in paragraph.text:
#                 paragraph.text = paragraph.text.replace('tenantshortsfp ', short_sfp)
        
#         # --- ТАБЛИЦА НА МЕСТО Table_readings ---
#         for i, paragraph in enumerate(doc.paragraphs):
#             if 'Table_readings' in paragraph.text:
#                 # Сохраняем родительский элемент и позицию
#                 parent = paragraph._element.getparent()
#                 index = parent.index(paragraph._element)
                
#                 # Удаляем параграф с плейсхолдером
#                 parent.remove(paragraph._element)
                
#                 # Создаем таблицу
#                 table = doc.add_table(rows=9, cols=6)
#                 add_borders_to_table(table)
#                 # Заполняем заголовки
#                 table.cell(0,0).text = "Услуга"
#                 table.cell(0,1).text = "Предыдущий"
#                 table.cell(0,2).text = "Текущий"
#                 table.cell(0,3).text = "Разница"
#                 table.cell(0,4).text = "Ставка"
#                 table.cell(0,5).text = "Сумма (руб.)"
                
#                 # Электроэнергия
#                 table.cell(1,0).text = "Электроэнергия (кВт·ч)"
#                 table.cell(1,1).text = str(final_list[0][0])
#                 table.cell(1,2).text = str(final_list[0][1])
#                 table.cell(1,3).text = str(final_list[0][2])
#                 table.cell(1,4).text = str(round(final_list[0][4],3))
#                 table.cell(1,5).text = str(final_list[0][3])
                
#                 # Холодная вода
#                 sum_cold_water = round(final_list[1][4], 3)*final_list[1][2]
#                 table.cell(2,0).text = "Холодная вода (м³)"
#                 table.cell(2,1).text = str(final_list[1][0])
#                 table.cell(2,2).text = str(final_list[1][1])
#                 table.cell(2,3).text = str(final_list[1][2])
#                 table.cell(2,4).text = str(round(final_list[1][4], 3))
#                 table.cell(2,5).text = str(sum_cold_water)
                
#                 # Горячая вода
#                 sum_hot_water = final_list[2][2]*round(final_list[2][4], 3)
#                 table.cell(3,0).text = "Горячая вода (м³)"
#                 table.cell(3,1).text = str(final_list[2][0])
#                 table.cell(3,2).text = str(final_list[2][1])
#                 table.cell(3,3).text = str(final_list[2][2])
#                 table.cell(3,4).text = str(round(final_list[2][4], 3))
#                 table.cell(3,5).text = str(sum_hot_water)
                
#                 print(f'Проверка на данные из отопления{final_list[3]}')
#                 # Отопление
#                 table.cell(4,0).text = "Отопление ()"
#                 table.cell(4,1).text = "—"
#                 table.cell(4,2).text = "—"
#                 table.cell(4,3).text = "—"
#                 table.cell(4,4).text = "—"
#                 table.cell(4,5).text = str(final_list[3][0])
                
#                 # Эксплуатационные услуги
#                 table.cell(5,0).text = "Эксплуатационные услуги"
#                 table.cell(5,1).text = "—"
#                 table.cell(5,2).text = "—"
#                 table.cell(5,3).text = "—"
#                 table.cell(5,4).text = "—"
#                 table.cell(5,5).text = str(price_for_user)
                
#                 # Водоотведение
#                 table.cell(6,0).text = "Водоотведение (м³)"
#                 table.cell(6,1).text = "—"
#                 table.cell(6,2).text = str(sum_drainage)
#                 table.cell(6,3).text = "—"
#                 table.cell(6,4).text = str(drainage_amount)
#                 table.cell(6,5).text = str(final_drainage_amount)
                
#                 table.cell(7,0).text = "Непредвиденные расходы"
#                 table.cell(7,1).text = ""
#                 table.cell(7,2).text = str(unexpected_expenses)
#                 table.cell(7,3).text = ""
#                 table.cell(7,4).text = ""
#                 table.cell(7,5).text = str(unexpected_expenses)

#                 # ИТОГО
#                 all_sum = round((float(final_drainage_amount) + float(unexpected_expenses) +
#                         float(price_for_user) + float(heat_sum) + float(final_list[3][0])+float(sum_hot_water)+float(sum_cold_water) +
#                         float(final_list[0][3])),2)
                
#                 table.cell(8,0).text = "ИТОГО К ОПЛАТЕ"
#                 table.cell(8,1).text = ""
#                 table.cell(8,2).text = ""
#                 table.cell(8,3).text = ""
#                 table.cell(8,4).text = ""
#                 table.cell(8,5).text = str(all_sum)
                
#                 # Вставляем таблицу на место удаленного параграфа
#                 parent.insert(index, table._element)
#                 break
        
#         # Сохраняем
#         doc.save(temp_path)
#         if os.path.exists(temp_path):
#             print(f"✅ Файл успешно создан: {temp_path}")
#             return temp_path # Возвращаем абсолютный путь к /tmp/file.docx
        
#     except Exception as e:
#         print(f"Ошибка: {e}")
#         import traceback
#         traceback.print_exc()
#         return None
import os
import math
import tempfile
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from shutil import copy2
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

async def create_word(id_us, count_users, all_indicators, all_information, unexpected_expenses, get_info_business, get_sheet_name):
    try:
        # 1. Подготовка базовых данных
        count_users = int(count_users)
        expl_amount = float(all_indicators['expl']['amount'])
        price_for_user = round((expl_amount / count_users), 2)
        
        records_list = await get_info_business(id_us)
        square, surname, first_name, patronymic, name_company, fodb_name = 0, "", "", "", "", ""
        if records_list:
            rec = records_list[0] # Берем первую запись
            square, surname, first_name, patronymic = rec.get('square', 0), rec.get('surname', ""), rec.get('first_name', ""), rec.get('patronymic', "")
            name_company, fodb_name = rec.get('name_company', ""), rec.get('fodb_name', "")

        short_sfp = f"{surname} {first_name[0] if first_name else ''}.{patronymic[0] if patronymic else ''}."
        full_sfp = f"{fodb_name} {name_company}"
        
        name_sheet = await get_sheet_name(id_us)
        base_path = os.getcwd()
        file_path = os.path.join(base_path, 'docs', 'ГИРА_1006теккаа2.xlsx')
        template_path = os.path.join(base_path, 'docs', 'Акт_расчета.docx')

        # 2. Чтение Excel (Linux не поддерживает xlwings/Excel, читаем напрямую)
        df = pd.read_excel(file_path, sheet_name=name_sheet, engine='openpyxl').fillna(0)
        curr, ago = datetime.now(), datetime.now() - relativedelta(months=1)
        dates = [datetime(curr.year, curr.month, 1).date(), datetime(ago.year, ago.month, 1).date()]
        
        found_cols = [df.columns.get_loc(c) for c in df.columns if isinstance(c, datetime) and c.date() in dates]
        if len(found_cols) < 2: return None

        data_rows = df.iloc[:, list(range(found_cols[0], found_cols[1] + 3))].values.tolist()
        list_data = []
        for i, row in enumerate(data_rows):
            if i == 0: continue
            if i % 2 == 0: list_data.append(row[5])
            else: 
                row.pop(2); row.pop(1)
                list_data.append(row)

        final_list, state = [], 1
        for i, val in enumerate(list_data):
            if state == 2:
                final_list[-1].append(val)
                state = 1
            else:
                if i > 5:
                    val = [val[1], val[3]] if (isinstance(val, list) and any(pd.isna(x) or (isinstance(x, float) and math.isnan(x)) for x in val)) else [val[3]]
                final_list.append(val)
                state += 1

        # 3. Расчеты
        dr_rate = float(all_indicators['drainage']['amount'])
        sum_dr = float(final_list[1][2]) + float(final_list[2][2])
        final_dr = round(sum_dr * dr_rate, 2)
        heat_val = round(float(final_list[3][1]) * float(final_list[3][0]), 2)

        # 4. Работа с Word (Создание временного файла для Linux)
        fd, temp_path = tempfile.mkstemp(suffix='.docx')
        os.close(fd)
        copy2(template_path, temp_path)
        doc = Document(temp_path)

        # Замены текста
        subs = {'tenant_sfp': full_sfp, 'start_day': str(all_information[1]),'thisday': str(all_information[0]), 'end_day': str(all_information[2]), 
                'monthyear': str(all_information[3]), 'square': str(square), 'tenantshortsfp': short_sfp}
        
        for p in doc.paragraphs:
            for k, v in subs.items():
                if k in p.text: p.text = p.text.replace(k, v)
        for p in doc.paragraphs:
            if 'Table_readings' in p.text:
                parent = p._element.getparent()
                idx = parent.index(p._element)
                parent.remove(p._element)
                
                table = doc.add_table(rows=9, cols=6)
                # Границы таблицы (inline)
                for cell in table._element.xpath('.//w:tc'):
                    tcPr = cell.get_or_add_tcPr()
                    borders = OxmlElement('w:tcBorders')
                    for b in ['top', 'left', 'bottom', 'right']:
                        edge = OxmlElement(f'w:{b}')
                        edge.set(qn('w:val'), 'single'), edge.set(qn('w:sz'), '4'), edge.set(qn('w:color'), '000000')
                        borders.append(edge)
                    tcPr.append(borders)

                # Заполнение
                headers = ["Услуга", "Предыдущий", "Текущий", "Разница", "Ставка", "Сумма (руб.)"]
                for j, h in enumerate(headers): table.cell(0, j).text = h

                rows_data = [
                    ["Электроэнергия (кВт·ч)", str(final_list[0][0]), str(final_list[0][1]), str(final_list[0][2]), str(round(final_list[0][4], 3)), str(final_list[0][3])],
                    ["Холодная вода (м³)", str(final_list[1][0]), str(final_list[1][1]), str(final_list[1][2]), str(round(final_list[1][4], 3)), str(round(final_list[1][4]*final_list[1][2], 2))],
                    ["Горячая вода (м³)", str(final_list[2][0]), str(final_list[2][1]), str(final_list[2][2]), str(round(final_list[2][4], 3)), str(round(final_list[2][4]*final_list[2][2], 2))],
                    ["Отопление", "—", "—", "—", "—", str(final_list[3][0])],
                    ["Эксплуатация", "—", "—", "—", "—", str(price_for_user)],
                    ["Водоотведение (м³)", "—", str(sum_dr), "—", str(dr_rate), str(final_dr)],
                    ["Непредвиденные", "—", str(unexpected_expenses), "—", "—", str(unexpected_expenses)]
                ]
                for r_idx, r_data in enumerate(rows_data, 1):
                    for c_idx, val in enumerate(r_data): table.cell(r_idx, c_idx).text = val

                all_sum = round(sum([float(r[5]) for r in rows_data if r[5] != "—"]) + heat_val, 2)
                table.cell(8, 0).text, table.cell(8, 5).text = "ИТОГО К ОПЛАТЕ", str(all_sum)
                parent.insert(idx, table._element)
                break

        doc.save(temp_path)
        return temp_path

    except Exception as e:
        print(f"Error: {e}"); return None