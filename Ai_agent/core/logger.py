import json
from datetime import datetime
from typing import Dict, Any

def decode_escaped_unicode_in_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        try:
            return json.loads(f'"{obj}"')
        except Exception:
            return obj
    elif isinstance(obj, dict):
        return {k: decode_escaped_unicode_in_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decode_escaped_unicode_in_obj(item) for item in obj]
    else:
        return obj

class Logger:
    """
    Логирование запросов и ответов агента.
    Поддерживает запись логов в файл.
    """
    
    def __init__(self, log_file: str = 'agent.log'):
        self.log_file = log_file

    def _get_timestamp(self) -> str:
        """Получить текущую метку времени."""
        return datetime.now().isoformat()

    def log(self, data: Dict[str, Any], log_type: str = "INFO"):
        """Записать лог."""
        log_entry = {
            'timestamp': self._get_timestamp(),
            'type': log_type,
            'data': data
        }
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    def log_request(self, request: Dict[str, Any]):
        """Записать лог запроса."""
        self.log({
            'message': 'Входящий запрос',
            'request': request
        }, "REQUEST")

    def log_response(self, response: Dict[str, Any]):
        """Записать лог ответа."""
        self.log({
            'message': 'Исходящий ответ',
            'response': response
        }, "RESPONSE")

    def log_error(self, error: str, context: Dict[str, Any] = None):
        """Записать лог ошибки."""
        self.log({
            'message': 'Произошла ошибка',
            'error': error,
            'context': context or {}
        }, "ERROR")

    def log_user_interaction(self, prompt: str, response: str):
        data = {
            'message': 'Взаимодействие с пользователем',
            'prompt': prompt,
            'response': response
        }
        # Раскодируем escape-последовательности Unicode в тексте перед логированием
        data = decode_escaped_unicode_in_obj(data)
        self.log(data, "USER_INTERACTION")
