import json
import os
from typing import Dict, Optional

# Путь к файлу для хранения данных пользователей
USER_DATA_FILE = "user_data.json"


def load_user(user_id: int) -> Dict:
    """
    Загружает данные пользователя из файла.
    
    Args:
        user_id (int): ID пользователя
        
    Returns:
        dict: Данные пользователя или пустой словарь, если пользователь не найден
    """
    # Если файл не существует, возвращаем пустой словарь
    if not os.path.exists(USER_DATA_FILE):
        return {}
    
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:  # Если файл пустой
                return {}
            data = json.loads(content)
            
        # Возвращаем данные конкретного пользователя или пустой словарь, если пользователя нет
        user_str_id = str(user_id)
        return data.get(user_str_id, {})
    except (json.JSONDecodeError, FileNotFoundError):
        # Если произошла ошибка при чтении файла, возвращаем пустой словарь
        return {}


def save_user(user_id: int, data: Dict) -> None:
    """
    Сохраняет данные пользователя в файл.
    
    Args:
        user_id (int): ID пользователя
        data (dict): Данные пользователя для сохранения
    """
    # Загружаем существующие данные
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:  # Если файл пустой
                all_data = {}
            else:
                all_data = json.loads(content)
    else:
        all_data = {}
    
    # Обновляем данные для конкретного пользователя
    user_str_id = str(user_id)
    all_data[user_str_id] = data
    
    # Сохраняем обновленные данные обратно в файл
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)