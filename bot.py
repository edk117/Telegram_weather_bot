import telebot
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import threading
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не установлен BOT_TOKEN")

# Импорт функций из weather_app
from weather_app import get_coordinates, get_current_weather, get_current_weather_by_city, get_forecast_5d3h, get_air_pollution, analyze_air_pollution
from storage import load_user, save_user

# Создание экземпляра бота
bot = telebot.TeleBot(BOT_TOKEN)

# Глобальная переменная для хранения состояния пользователей
user_states = {}

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = get_main_menu_keyboard()
    bot.reply_to(message, "Привет! Я бот для просмотра погоды. Выберите одну из опций:", reply_markup=markup)

# Список кнопок меню, которые не должны обрабатываться как текст
MENU_BUTTONS = ["Текущая погода", "Прогноз на 5 дней", "Моя геолокация", "Сравнить города",
                "Расширенные данные", "Уведомления", "Назад в меню", "Главное меню", "Подписаться на уведомления",
                "Отписаться от уведомлений"]

def is_menu_button(text):
    """Проверяет, является ли текст кнопкой меню"""
    if not text:
        return False
    return any(text == btn or text.startswith(btn) for btn in MENU_BUTTONS)


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Создаёт клавиатуру главного меню"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("Текущая погода"), KeyboardButton("Прогноз на 5 дней"))
    markup.row(KeyboardButton("Моя геолокация"), KeyboardButton("Сравнить города"))
    markup.row(KeyboardButton("Расширенные данные"), KeyboardButton("Уведомления"))
    return markup

# Обработка команды "Текущая погода"
@bot.message_handler(func=lambda message: message.text == "Текущая погода")
def current_weather_request(message):
    msg = bot.reply_to(message, "Введите название города:")
    bot.register_next_step_handler(msg, process_city_input_for_current_weather)

def process_city_input_for_current_weather(message):
    # Игнорируем кнопки меню
    if is_menu_button(message.text):
        return

    city = message.text
    # Используем прямой запрос по названию города для правильного названия
    weather_data = get_current_weather_by_city(city)
    if weather_data:
        response = format_current_weather(weather_data)
        # Сохраняем координаты для будущего использования
        lat = weather_data['coord']['lat']
        lon = weather_data['coord']['lon']
        user_id = message.from_user.id
        user_data = load_user(user_id)
        user_data['location'] = [lat, lon]
        save_user(user_id, user_data)

        # Возвращаем главное меню после показа погоды
        markup = get_main_menu_keyboard()
        bot.reply_to(message, response, reply_markup=markup)
    else:
        bot.reply_to(message, "Город не найден. Попробуйте еще раз.")

# Форматирование текущей погоды
def format_current_weather(data):
    city = data['name']
    country = data['sys']['country']
    temp = data['main']['temp']
    feels_like = data['main']['feels_like']
    humidity = data['main']['humidity']
    pressure = data['main']['pressure']
    wind_speed = data['wind']['speed']
    description = data['weather'][0]['description'].capitalize()
    
    response = f"🌤️ Погода в {city}, {country}:\n"
    response += f"🌡️ Температура: {temp}°C (ощущается как {feels_like}°C)\n"
    response += f"💧 Влажность: {humidity}%\n"
    response += f"🔽 Давление: {pressure} гПа\n"
    response += f"💨 Ветер: {wind_speed} м/с\n"
    response += f"📝 Описание: {description}\n"
    
    return response

# Обработка команды "Прогноз на 5 дней"
@bot.message_handler(func=lambda message: message.text == "Прогноз на 5 дней")
def forecast_5days_request(message):
    user_id = message.from_user.id
    user_data = load_user(user_id)

    if 'location' in user_data:
        lat, lon = user_data['location']
        # Получаем название города из координат
        weather_data = get_current_weather(lat, lon)
        city_name = weather_data['name'] if weather_data else None
        send_forecast_inline(message, lat, lon, city_name)
    else:
        msg = bot.reply_to(message, "Введите название города для прогноза на 5 дней:")
        bot.register_next_step_handler(msg, process_city_input_for_forecast)

def process_city_input_for_forecast(message):
    # Игнорируем кнопки меню
    if is_menu_button(message.text):
        return

    city = message.text
    # Сначала получаем погоду по городу для правильных координат
    weather_data = get_current_weather_by_city(city)
    if weather_data:
        lat = weather_data['coord']['lat']
        lon = weather_data['coord']['lon']
        city_name = weather_data['name']
        # Сохраняем координаты
        user_id = message.from_user.id
        user_data = load_user(user_id)
        user_data['location'] = [lat, lon]
        save_user(user_id, user_data)
        send_forecast_inline(message, lat, lon, city_name)
    else:
        bot.reply_to(message, "Город не найден. Попробуйте еще раз.")

def send_forecast_inline(message, lat, lon, city_name=None):
    forecast_list = get_forecast_5d3h(lat, lon)
    if not forecast_list:
        bot.reply_to(message, "Не удалось получить прогноз погоды.")
        return

    # Если название города не передано, получаем его из API погоды
    if not city_name:
        weather_data = get_current_weather(lat, lon)
        city_name = weather_data['name'] if weather_data else f"Координаты ({lat}, {lon})"

    # Группируем прогноз по дням
    daily_forecasts = {}
    for item in forecast_list:
        date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
        if date not in daily_forecasts:
            daily_forecasts[date] = []
        daily_forecasts[date].append(item)

    # Создаем inline-клавиатуру с днями
    markup = InlineKeyboardMarkup()
    for date in sorted(daily_forecasts.keys())[:5]:  # Только первые 5 дней
        day_name = datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m')
        button = InlineKeyboardButton(f"{day_name}", callback_data=f"day_{date}_{lat}_{lon}")
        markup.add(button)

    bot.reply_to(message, f"📅 Прогноз погоды: {city_name}\n\nВыберите день для просмотра прогноза:", reply_markup=markup)

# Обработка нажатий на inline-кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data.startswith("day_"):
        # Формат: day_{date}_{lat}_{lon}
        parts = call.data.split("_")
        date = parts[1]  # 2026-03-23 (содержит -, а не _)
        lat = float(parts[2])
        lon = float(parts[3])
        
        # Получаем прогноз для выбранного дня
        forecast_list = get_forecast_5d3h(lat, lon)
        if not forecast_list:
            bot.answer_callback_query(call.id, "Не удалось получить прогноз погоды.")
            return
        
        # Фильтруем прогноз для выбранного дня
        day_forecasts = [item for item in forecast_list if datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d') == date]
        
        # Форматируем информацию о дне
        day_name = datetime.strptime(date, '%Y-%m-%d').strftime('%d %B %Y')
        response = f"Прогноз на {day_name}:\n\n"
        for item in day_forecasts:
            time_str = datetime.fromtimestamp(item['dt']).strftime('%H:%M')
            temp = item['main']['temp']
            desc = item['weather'][0]['description'].capitalize()
            response += f"{time_str}: {temp}°C, {desc}\n"
        
        # Создаем клавиатуру с кнопкой "Назад"
        markup = InlineKeyboardMarkup()
        back_button = InlineKeyboardButton("Назад", callback_data=f"back_to_days_{lat}_{lon}")
        markup.add(back_button)
        
        # Редактируем сообщение с новым содержимым и клавиатурой
        bot.edit_message_text(chat_id=call.message.chat.id,
                             message_id=call.message.message_id,
                             text=response,
                             reply_markup=markup)
    
    elif call.data.startswith("back_to_days_"):
        # Формат: back_to_days_{lat}_{lon}
        coords = call.data.replace("back_to_days_", "")
        lat, lon = map(float, coords.split("_"))

        # Отправляем заново клавиатуру с днями
        forecast_list = get_forecast_5d3h(lat, lon)
        if not forecast_list:
            bot.answer_callback_query(call.id, "Не удалось получить прогноз погоды.")
            return

        # Группируем прогноз по дням
        daily_forecasts = {}
        for item in forecast_list:
            date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
            if date not in daily_forecasts:
                daily_forecasts[date] = []
            daily_forecasts[date].append(item)

        # Создаем inline-клавиатуру с днями
        markup = InlineKeyboardMarkup()
        for date in sorted(daily_forecasts.keys())[:5]:  # Только первые 5 дней
            day_name = datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m')
            button = InlineKeyboardButton(f"{day_name}", callback_data=f"day_{date}_{lat}_{lon}")
            markup.add(button)

        # Редактируем сообщение с клавиатурой дней
        bot.edit_message_text(chat_id=call.message.chat.id,
                             message_id=call.message.message_id,
                             text="Выберите день для просмотра прогноза:",
                             reply_markup=markup)

# Обработка команды "Моя геолокация"
@bot.message_handler(func=lambda message: message.text == "Моя геолокация")
def request_location(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("Отправить местоположение", request_location=True))
    bot.reply_to(message, "Нажмите на кнопку ниже, чтобы отправить ваше местоположение:", reply_markup=markup)

# Обработка полученного местоположения
@bot.message_handler(content_types=['location'])
def handle_location(message):
    lat = message.location.latitude
    lon = message.location.longitude
    
    # Сохраняем местоположение пользователя
    user_id = message.from_user.id
    user_data = load_user(user_id)
    user_data['location'] = [lat, lon]
    save_user(user_id, user_data)
    
    # Получаем и отправляем погоду для этого местоположения
    weather_data = get_current_weather(lat, lon)
    if weather_data:
        response = format_current_weather(weather_data)
        # Возвращаем главное меню
        markup = get_main_menu_keyboard()
        bot.reply_to(message, response, reply_markup=markup)
    else:
        bot.reply_to(message, "Не удалось получить данные о погоде для этого местоположения.")

# Обработка команды "Сравнить города"
@bot.message_handler(func=lambda message: message.text == "Сравнить города")
def compare_cities_request(message):
    msg = bot.reply_to(message, "Введите первый город:")
    bot.register_next_step_handler(msg, process_first_city_for_comparison)

def process_first_city_for_comparison(message):
    # Игнорируем кнопки меню
    if is_menu_button(message.text):
        return
    
    user_id = message.from_user.id
    user_states[user_id] = {'first_city': message.text}
    msg = bot.reply_to(message, "Введите второй город:")
    bot.register_next_step_handler(msg, process_second_city_for_comparison)

def process_second_city_for_comparison(message):
    user_id = message.from_user.id
    if user_id not in user_states or 'first_city' not in user_states[user_id]:
        bot.reply_to(message, "Произошла ошибка. Начните сначала.")
        return

    # Игнорируем кнопки меню
    if is_menu_button(message.text):
        return

    second_city = message.text
    first_city = user_states[user_id]['first_city']

    # Получаем погоду для обоих городов напрямую по названию
    weather1 = get_current_weather_by_city(first_city)
    weather2 = get_current_weather_by_city(second_city)

    if not weather1:
        bot.reply_to(message, f"Город '{first_city}' не найден.")
        return

    if not weather2:
        bot.reply_to(message, f"Город '{second_city}' не найден.")
        return

    if not weather1 or not weather2:
        bot.reply_to(message, "Не удалось получить данные о погоде для одного из городов.")
        return
    
    # Форматируем таблицу сравнения
    response = format_cities_comparison(first_city, weather1, second_city, weather2)
    # Возвращаем главное меню
    markup = get_main_menu_keyboard()
    bot.reply_to(message, response, reply_markup=markup)

    # Очищаем состояние пользователя
    if user_id in user_states:
        del user_states[user_id]

def format_cities_comparison(city1, weather1, city2, weather2):
    temp1 = weather1['main']['temp']
    temp2 = weather2['main']['temp']
    feels_like1 = weather1['main']['feels_like']
    feels_like2 = weather2['main']['feels_like']
    humidity1 = weather1['main']['humidity']
    humidity2 = weather2['main']['humidity']
    wind1 = weather1['wind']['speed']
    wind2 = weather2['wind']['speed']
    desc1 = weather1['weather'][0]['description']
    desc2 = weather2['weather'][0]['description']
    
    # Определяем, где теплее
    diff = temp1 - temp2
    if diff > 0:
        warmer = f"🔥 В {city1} теплее на {abs(diff):.1f}°C"
    elif diff < 0:
        warmer = f"🔥 В {city2} теплее на {abs(diff):.1f}°C"
    else:
        warmer = "🤝 Температура одинаковая"

    response = f"📊 Сравнение погоды\n\n"
    response += f"{'🏙️':<2} {city1:<15} │ {city2:<15} {'🏙️':>2}\n"
    response += f"{'─'*20}┼{'─'*17}\n"
    response += f"🌡️ Температура    │ {temp1:>6.1f}°C       │ {temp2:>6.1f}°C\n"
    response += f"🤔 Ощущается как  │ {feels_like1:>6.1f}°C       │ {feels_like2:>6.1f}°C\n"
    response += f"💧 Влажность      │ {humidity1:>6}%        │ {humidity2:>6}%\n"
    response += f"💨 Ветер          │ {wind1:>6.1f} м/с     │ {wind2:>6.1f} м/с\n"
    response += f"📝 Погода         │ {desc1.capitalize():<14} │ {desc2.capitalize():<14}\n"
    response += f"\n{warmer}"

    return response

# Обработка команды "Расширенные данные"
@bot.message_handler(func=lambda message: message.text == "Расширенные данные")
def advanced_weather_request(message):
    msg = bot.reply_to(message, "Введите название города или отправьте местоположение:")
    bot.register_next_step_handler(msg, process_city_input_for_advanced_weather)

def process_city_input_for_advanced_weather(message):
    # Проверяем, является ли сообщение местоположением
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        send_advanced_weather(message, lat, lon)
    else:
        # Игнорируем кнопки меню
        if is_menu_button(message.text):
            return

        city = message.text
        # Используем прямой запрос по названию города
        weather_data = get_current_weather_by_city(city)
        if weather_data:
            lat = weather_data['coord']['lat']
            lon = weather_data['coord']['lon']
            send_advanced_weather(message, lat, lon)
        else:
            bot.reply_to(message, "Город не найден. Попробуйте еще раз.")

def send_advanced_weather(message, lat, lon):
    # Получаем основные данные о погоде
    weather_data = get_current_weather(lat, lon)
    if not weather_data:
        bot.reply_to(message, "Не удалось получить данные о погоде.")
        return
    
    # Получаем данные о загрязнении воздуха
    pollution_data = get_air_pollution(lat, lon)
    if not pollution_data:
        bot.reply_to(message, "Не удалось получить данные о загрязнении воздуха.")
        return
    
    # Анализируем загрязнение воздуха
    components = pollution_data['list'][0]['components'] if pollution_data.get('list') else {}
    pollution_analysis = analyze_air_pollution(components, extended=True)
    
    # Форматируем расширенные данные
    response = format_advanced_weather(weather_data, pollution_analysis)
    # Возвращаем главное меню
    markup = get_main_menu_keyboard()
    bot.reply_to(message, response, reply_markup=markup)

def format_advanced_weather(weather_data, pollution_analysis):
    city = weather_data['name']
    country = weather_data['sys']['country']
    temp = weather_data['main']['temp']
    feels_like = weather_data['main']['feels_like']
    humidity = weather_data['main']['humidity']
    pressure = weather_data['main']['pressure']
    wind_speed = weather_data['wind']['speed']
    wind_deg = weather_data['wind'].get('deg', 0)
    visibility = weather_data.get('visibility', 0) / 1000  # в км
    clouds = weather_data['clouds']['all']
    sunrise = datetime.fromtimestamp(weather_data['sys']['sunrise']).strftime('%H:%M')
    sunset = datetime.fromtimestamp(weather_data['sys']['sunset']).strftime('%H:%M')
    description = weather_data['weather'][0]['description'].capitalize()
    
    # Данные о загрязнении воздуха
    air_status = pollution_analysis['status'] if pollution_analysis else "Нет данных"
    air_values = pollution_analysis['values'] if pollution_analysis else {}
    
    response = f"🌍 Погода в {city}, {country}:\n\n"
    response += f"🌡️ Температура: {temp}°C (ощущается как {feels_like}°C)\n"
    response += f"💧 Влажность: {humidity}%\n"
    response += f"🔽 Давление: {pressure} гПа\n"
    response += f"💨 Ветер: {wind_speed} м/с, направление: {wind_deg}°\n"
    response += f"👁️ Видимость: {visibility} км\n"
    response += f"☁️ Облачность: {clouds}%\n"
    response += f"🌅 Восход: {sunrise}\n"
    response += f"🌇 Закат: {sunset}\n"
    response += f"📝 Описание: {description}\n\n"
    response += f"🍃 Качество воздуха: {air_status}\n"
    if air_values:
        response += f"  • Угарный газ (CO): {air_values.get('co', 0)} μg/m³\n"
        response += f"  • Диоксид азота (NO₂): {air_values.get('no2', 0)} μg/m³\n"
        response += f"  • Озон (O₃): {air_values.get('o3', 0)} μg/m³\n"
        response += f"  • PM2.5: {air_values.get('pm2_5', 0)} μg/m³\n"
        response += f"  • PM10: {air_values.get('pm10', 0)} μg/m³\n"
        response += f"  • Аммиак (NH₃): {air_values.get('nh3', 0)} μg/m³\n"
    
    return response

# Обработка команды "Уведомления"
@bot.message_handler(func=lambda message: message.text == "Уведомления")
def notifications_request(message):
    user_id = message.from_user.id
    user_data = load_user(user_id)
    is_subscribed = user_data.get('notifications', {}).get('enabled', False)
    interval = user_data.get('notifications', {}).get('interval', 2)

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    if is_subscribed:
        markup.row(KeyboardButton("Отписаться от уведомлений"))
        markup.row(KeyboardButton(f"Интервал: {interval} ч"))
    else:
        markup.row(KeyboardButton("Подписаться на уведомления"))
    
    markup.row(KeyboardButton("Главное меню"))

    status = "включены" if is_subscribed else "отключены"
    bot.reply_to(message, f"Уведомления сейчас {status}.\nТекущий интервал: {interval} часа.", reply_markup=markup)

# Обработка подписки на уведомления
@bot.message_handler(func=lambda message: message.text == "Подписаться на уведомления")
def subscribe_notifications(message):
    user_id = message.from_user.id
    user_data = load_user(user_id)
    if 'notifications' not in user_data:
        user_data['notifications'] = {}
    user_data['notifications']['enabled'] = True
    user_data['notifications']['interval'] = 2  # по умолчанию 2 часа
    save_user(user_id, user_data)
    
    bot.reply_to(message, "Вы подписались на уведомления о погоде! Уведомления будут приходить каждые 2 часа.")

@bot.message_handler(func=lambda message: message.text == "Отписаться от уведомлений")
def unsubscribe_notifications(message):
    user_id = message.from_user.id
    user_data = load_user(user_id)
    if 'notifications' not in user_data:
        user_data['notifications'] = {}
    user_data['notifications']['enabled'] = False
    save_user(user_id, user_data)
    
    bot.reply_to(message, "Вы отписались от уведомлений о погоде.")

@bot.message_handler(func=lambda message: message.text.startswith("Интервал: "))
def change_notification_interval(message):
    user_id = message.from_user.id
    user_data = load_user(user_id)
    current_interval = user_data.get('notifications', {}).get('interval', 2)

    # Предлагаем варианты интервалов
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    intervals = [1, 2, 4, 6, 12]
    for interval in intervals:
        if interval != current_interval:
            markup.row(KeyboardButton(f"Установить интервал: {interval} ч"))
    markup.row(KeyboardButton("Главное меню"))

    bot.reply_to(message, f"Текущий интервал уведомлений: {current_interval} часа.\nВыберите новый интервал:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text.startswith("Установить интервал: "))
def set_notification_interval(message):
    try:
        new_interval = int(message.text.split(": ")[1].split(" ")[0])
        user_id = message.from_user.id
        user_data = load_user(user_id)
        if 'notifications' not in user_data:
            user_data['notifications'] = {}
        user_data['notifications']['interval'] = new_interval
        save_user(user_id, user_data)
        
        bot.reply_to(message, f"Интервал уведомлений установлен на {new_interval} часа(ов).")
    except (ValueError, IndexError):
        bot.reply_to(message, "Произошла ошибка при установке интервала. Попробуйте снова.")

@bot.message_handler(func=lambda message: message.text == "Назад в меню")
@bot.message_handler(func=lambda message: message.text == "Главное меню")
def back_to_menu(message):
    markup = get_main_menu_keyboard()
    bot.reply_to(message, "Вы вернулись в главное меню.", reply_markup=markup)

# Функция для проверки необходимости отправки уведомлений
def check_and_send_notifications():
    while True:
        time.sleep(60)  # Проверяем каждую минуту
        
        # Получаем всех пользователей
        if os.path.exists("user_data.json"):
            with open("user_data.json", "r") as f:
                all_users = json.load(f)
        else:
            continue
        
        current_time = time.time()
        for user_id_str, user_data in all_users.items():
            user_id = int(user_id_str)
            notifications_config = user_data.get('notifications', {})
            if notifications_config.get('enabled', False):
                last_notification = user_data.get('last_notification', 0)
                interval_hours = notifications_config.get('interval', 2)
                interval_seconds = interval_hours * 3600
                
                if current_time - last_notification >= interval_seconds:
                    # Отправляем уведомление пользователю
                    if 'location' in user_data:
                        lat, lon = user_data['location']
                        weather_data = get_current_weather(lat, lon)
                        if weather_data:
                            response = format_current_weather(weather_data)
                            try:
                                bot.send_message(user_id, f"🌤️ Уведомление о погоде:\n{response}")
                                # Обновляем время последнего уведомления
                                user_data['last_notification'] = current_time
                                save_user(user_id, user_data)
                            except Exception as e:
                                error_msg = str(e)
                                # Если чат не найден (пользователь заблокировал бота), удаляем его из базы
                                if "chat not found" in error_msg or "blocked" in error_msg:
                                    print(f"Пользователь {user_id} заблокировал бота или удалил чат. Удаляем из базы.")
                                    try:
                                        all_users = json.load(open("user_data.json", "r"))
                                        if str(user_id) in all_users:
                                            del all_users[str(user_id)]
                                            with open("user_data.json", "w") as f:
                                                json.dump(all_users, f, ensure_ascii=False, indent=2)
                                    except Exception as del_error:
                                        print(f"Ошибка при удалении пользователя {user_id}: {del_error}")
                                else:
                                    print(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
                    else:
                        # Если у пользователя нет сохраненного местоположения, отправляем запрос
                        try:
                            bot.send_message(user_id, "🌤️ Время получения уведомления о погоде, но у вас не установлено местоположение. Пожалуйста, обновите его в разделе 'Моя геолокация'.")
                            user_data['last_notification'] = current_time
                            save_user(user_id, user_data)
                        except Exception as e:
                            error_msg = str(e)
                            # Если чат не найден (пользователь заблокировал бота), удаляем его из базы
                            if "chat not found" in error_msg or "blocked" in error_msg:
                                print(f"Пользователь {user_id} заблокировал бота или удалил чат. Удаляем из базы.")
                                try:
                                    all_users = json.load(open("user_data.json", "r"))
                                    if str(user_id) in all_users:
                                        del all_users[str(user_id)]
                                        with open("user_data.json", "w") as f:
                                            json.dump(all_users, f, ensure_ascii=False, indent=2)
                                except Exception as del_error:
                                    print(f"Ошибка при удалении пользователя {user_id}: {del_error}")
                            else:
                                print(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")

# Запуск проверки уведомлений в отдельном потоке
notification_thread = threading.Thread(target=check_and_send_notifications, daemon=True)
notification_thread.start()

# Запуск бота
if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True)

