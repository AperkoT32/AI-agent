from typing import Dict, Any
from datetime import datetime
import json
import os
import gzip
import shutil

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

    
    def __init__(self, log_file: str = 'agent.log', max_size_mb: int = 10, backup_count: int = 5):
        self.log_file = log_file
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.backup_count = backup_count
        self._check_log_size()

    def _get_timestamp(self) -> str:
        """Получить текущую метку времени."""
        return datetime.now().isoformat()
    
    def _check_log_size(self):
        if not os.path.exists(self.log_file):
            return
        if os.path.getsize(self.log_file) >= self.max_size_bytes:
            self._rotate_logs()
    
    def _rotate_logs(self):
        oldest_backup = f"{self.log_file}.{self.backup_count}.gz"
        if os.path.exists(oldest_backup):
            os.remove(oldest_backup)
            for i in range(self.backup_count - 1, 0, -1):
                src = f"{self.log_file}.{i}.gz"
                dst = f"{self.log_file}.{i+1}.gz"
                if os.path.exists(src):
                    os.rename(src, dst)

            with open(self.log_file, 'rb') as f_in:
                with gzip.open(oldest_backup, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            open(self.log_file, 'w').close()

            print(f"Выполнена ротация лог-файла {self.log_file}")

    def log(self, data: Dict[str, Any], log_type: str = "INFO"):

        self._check_log_size()

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
