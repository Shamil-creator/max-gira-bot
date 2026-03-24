import requests
from main import bot, y, client
import os
import pandas as pd

def get_yandex_disk_token(client_id, client_secret, authorization_code):
    url = "https://oauth.yandex.ru/token"
    data = {
        'grant_type': 'authorization_code',
        'code': authorization_code,
        'client_id': client_id,
        'client_secret': client_secret
    }
    
    response = requests.post(url, data=data)
    return response.json()

def check_yes_or_no_company(word):
    try:
        items = list(y.listdir("/ARIT"))
        for item in items:
            if 'Реестр Арендаторов ИБРАГИМОВА 61(ГИРА).xlsx' == item.name:
                local_filename = item.name
                y.download(item.path, local_filename)
                file_path = local_filename
                print('Файл найден и отправлен')
                break
        df = pd.read_excel(file_path)
        column_name = 'Арендатор'
        contains_word = df[column_name].astype(str).str.contains(word,na=False)
        if contains_word.any():
            print(f"Нашли компанию")
            return True
        else:
            print(f"Не нашли компанию")
            return False
    finally:
            if os.path.exists(local_filename):
                os.remove(local_filename)

def check_file():
    if y.check_token():
        try:
            
            disk_info = y.get_disk_info()

            print("Доступные атрибуты disk_info:")
            for attr in dir(disk_info):
                if not attr.startswith('_'):
                    value = getattr(disk_info, attr)
                    if not callable(value):
                        print(f"  {attr}: {value}")
            
            print("\n=== СОДЕРЖИМОЕ ДИСКА ===")
            
            # Проверяем содержимое
            items = list(y.listdir("/ARIT/Действующие Арендаторы. Договора"))
            print(f"Элементов в корне: {len(items)}")
            
            for item in items:
                print(f"- {item.name} ({item.type})")
                name_docx = item.name
                if 'Реестр Арендаторов ИБРАГИМОВА 61(ГИРА).xlsx' == item.name:
                    local_filename = item.name
                    y.download(item.path, local_filename)
                    
                    # Создаем объект FSInputFile и отправляем напрямую
                    # document = FSInputFile(local_filename)
                    pass
                    
                    print('Файл найден и отправлен')
                    break
                
        except Exception as e:
            print(f"Ошибка: {e}")
        finally:
        # Удаляем файл в любом случае
            if os.path.exists(local_filename):
                os.remove(local_filename)
    else:
        pass