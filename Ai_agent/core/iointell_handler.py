import requests
import json
from typing import Dict, Any, Optional
from core.logger import Logger

class APIHandler:
    def __init__(self, config_path: str = 'config.json', log_file: str = 'APIHandler.log'):
        self.logger = Logger(log_file)
        config = self._load_config(config_path)
        
        self.api_key = config.get('api_key')
        self.base_url = config.get('base_url')
        if not self.base_url:
            raise ValueError("В config.json не задан base_url")
        
        if not self.api_key:
            raise ValueError("Ключ API должен быть в config.json.")
        
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        })

    def _load_config(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.log_error(f"Конфиг не найден: {path}")
            raise
        except json.JSONDecodeError as e:
            self.logger.log_error(f"Недопустимый json конфиг: {e}")
            raise

    def get_models(self) -> Dict[str, Any]:
        url = f"{self.base_url}/models"
        self.logger.log_request({'url': url, 'method': 'GET'})
        try:
            response = self.session.get(url)
            response.raise_for_status()
            result = response.json()
            self.logger.log_response(result)
            return result
        except requests.exceptions.RequestException as e:
            self.logger.log_error(f"Ошибка при получении моделей: {str(e)}")
            raise

    def process_request(self, endpoint: str, method: str = 'POST', params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        self.logger.log_request({'url': url, 'method': method, 'params': params})
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=params)
            else:
                raise ValueError(f"Метод '{method}' не поддерживается.")

            response.raise_for_status()
            result = response.json()
            self.logger.log_response(result)
            return result
        except requests.exceptions.RequestException as e:
            self.logger.log_error(f"Ошибка при запросе к {url}: {str(e)}")
            raise 