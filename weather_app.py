import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")


def _make_request(url: str, max_retries: int = 3) -> requests.Response | None:
    """HTTP-запрос с повторами при ошибках 429 и сетевых проблемах"""
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url)
            if response.status_code == 429:
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                return response
            return response
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise
    return None


def _request_weather(params: dict) -> dict | None:
    """Универсальный запрос к Weather API"""
    if not API_KEY:
        return None
    
    params['appid'] = API_KEY
    params['units'] = 'metric'
    params['lang'] = 'ru'
    
    try:
        response = _make_request(f"https://api.openweathermap.org/data/2.5/weather?{'&'.join(f'{k}={v}' for k, v in params.items())}")
        return response.json() if response and response.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None


def get_coordinates(city: str, limit: int = 5) -> tuple[float, float] | None:
    """Получает координаты города с приоритетом России"""
    if not API_KEY:
        return None

    for query in [f"{city},RU", city]:
        try:
            response = _make_request(
                f"https://api.openweathermap.org/geo/1.0/direct?q={query}&appid={API_KEY}&limit={limit}&lang=ru"
            )
            if response and response.status_code == 200:
                data = response.json()
                if data:
                    # Предпочитаем города с населением
                    for item in data:
                        if item.get('pop', 0) > 0:
                            return float(item['lat']), float(item['lon'])
                    return float(data[0]['lat']), float(data[0]['lon'])
        except requests.exceptions.RequestException:
            continue
    return None


def get_current_weather(lat: float, lon: float) -> dict | None:
    """Получает погоду по координатам"""
    return _request_weather({'lat': lat, 'lon': lon})


def get_current_weather_by_city(city: str) -> dict | None:
    """Получает погоду по названию города (с приоритетом России)"""
    for query in [f"{city},RU", city]:
        result = _request_weather({'q': query})
        if result:
            return result
    return None


def get_forecast_5d3h(lat: float, lon: float) -> list[dict]:
    """Прогноз погоды на 5 дней"""
    if not API_KEY:
        return []
    
    try:
        response = _make_request(
            f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=ru"
        )
        return response.json().get('list', []) if response and response.status_code == 200 else []
    except requests.exceptions.RequestException:
        return []


def get_air_pollution(lat: float, lon: float) -> dict | None:
    """Данные о загрязнении воздуха"""
    if not API_KEY:
        return None
    
    try:
        response = _make_request(
            f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        )
        return response.json() if response and response.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None


def analyze_air_pollution(components: dict, extended: bool = False) -> dict | None:
    """Анализ загрязнения воздуха"""
    if not components:
        return None

    # Пороги WHO/EPA
    thresholds = {
        'pm2_5': (25, 37.5, 50),
        'pm10': (50, 75, 100),
        'o3': (120, 180, 240),
        'no2': (25, 37.5, 50),
        'co': (4.4, 6.6, 8.8),
        'nh3': (200, 300, 400)
    }

    def get_level(value: float, limits: tuple) -> str:
        if value <= limits[0]:
            return 'Хорошее'
        elif value <= limits[1]:
            return 'Умеренное'
        elif value <= limits[2]:
            return 'Нездоровое'
        return 'Опасное'

    values = {k: components.get(k, 0) for k in thresholds}
    levels = {k: get_level(v, thresholds[k]) for k, v in values.items()}
    
    # Общий статус - худший из всех
    status = 'Хорошее'
    if 'Опасное' in levels.values():
        status = 'Опасное'
    elif 'Нездоровое' in levels.values():
        status = 'Нездоровое'
    elif 'Умеренное' in levels.values():
        status = 'Умеренное'

    return {
        'status': status,
        'components_levels': levels if extended else None,
        'values': values
    }
