import queue
import threading
import base64
import os
import json
from typing import Dict, Any
from .queue_manager import QueueManager
from .api_handler import APIHandler
from .logger import Logger
from.iointell_handler import APIHandler  
#from .openai_handler import OpenAIHandler
global current_image_path

class AIAgent:
    def __init__(self, log_file: str = 'agent.log', config_path: str = 'config.json'):
        self.queue_manager = QueueManager()
        self.api_handler = APIHandler()
        self.logger = Logger(log_file)
        # self.openai_handler = OpenAIHandler(config_path)     # Если хотим через сам чат ГПТ + ПЛАТИТЬ ДЕНЮЖКУ
        self.iointelligence_handler = None
        self._running = False
        self._worker_thread = None

        config = self.load_config(config_path)  # Используем load_config
        if 'api_key' in config:
            self.iointelligence_handler = APIHandler(config_path='config.json')

    def encode_image_to_base64(self, image_path: str) -> str:
        if not os.path.isfile(image_path):
            self.logger.log_error(f"Файл изображения не найден: {image_path}")
            raise FileNotFoundError(f"Файл изображения не найден: {image_path}")
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode("utf-8")
        return encoded
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Загружает конфигурацию из JSON файла."""
        import json
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            self.logger.log_error(f"json не найден: {config_path}") # *** ЛОГИРОВАНИЕ
            return {}
        except json.JSONDecodeError:
            self.logger.log_error(f"неправильный json формат: {config_path}") # *** ЛОГИРОВАНИЕ
            return {}

    def register_api(self, name: str, handler: callable):
        """Регистрация API обработчика."""
        self.api_handler.register_api(name, handler)
        self.logger.log({
            'message': 'Зарегистрированный обработчик API',
            'api_name': name
        }) # *** ЛОГИРОВАНИЕ

    def register_api_module(self, module_path: str):
        """Регистрация модуля с API обработчиками."""
        self.api_handler.register_api_module(module_path)
        self.logger.log({
            'message': 'Зарегистрированный модуль API',
            'module_path': module_path
        }) # *** ЛОГИРОВАНИЕ

    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self.logger.log_request(request) # *** ЛОГИРОВАНИЕ

            if 'api' not in request:
                raise ValueError("В запросе должен быть указан  'api'")

            api_name = request['api']

            if api_name == 'iointelligence':
                if not self.iointelligence_handler:
                    raise ValueError("IOIntel ключ API не настроен.")
            
            #if api_name == 'openai':                      # Если хотим через сам чат ГПТ + ПЛАТИТЬ ДЕНЮЖКУ
            #    response = self.openai_handler.process_agent_request(request)        # Если хотим через сам чат ГПТ + ПЛАТИТЬ ДЕНЮЖКУ
            if api_name == 'iointelligence':
                if not self.iointelligence_handler:
                    raise ValueError("IOIntel ключ API не настроен.")
                endpoint = request.get('endpoint')
                params = request.get('params', {})
                method = request.get('method', 'POST')  # По умолчанию используем POST

                # Вызываем process_request с указанием метода
                result = self.iointelligence_handler.process_request(endpoint=endpoint, method=method, params=params)
                self.logger.log({
                    'message': 'Результат от iointelligence_handler.process_request',
                    'result': result
                }, 'DEBUG') # *** ЛОГИРОВАНИЕ
                response = {
                    'status': 'success',
                    'request_id': request.get('request_id'),
                    'data': result
                }
            else:
                handler = self.api_handler.get_api(api_name)

                # Вызываем обработчик с параметрами из запроса
                result = handler(**request.get('params', {}))

                response = {
                    'status': 'success',
                    'request_id': request.get('request_id'),
                    'data': result
                }

            self.logger.log_response(response) # *** ЛОГИРОВАНИЕ
            return response

        except Exception as e:
            error_response = {
                'status': 'error',
                'request_id': request.get('request_id'),
                'error': str(e)
            }
            self.logger.log_error(str(e), {'request': request}) # *** ЛОГИРОВАНИЕ
            return error_response

    def _worker_loop(self):
        while self._running:
            try:
                self.logger.log({"message": "Ожидаем запрос из очереди"}, "DEBUG")
                request = self.queue_manager.get_request(timeout=0.1) # *** ЛОГИРОВАНИЕ
                self.logger.log({"message": "Получен запрос из очереди", "request_id": request.get("request_id")},
                                "DEBUG")
                response = self.process_request(request) # *** ЛОГИРОВАНИЕ
                self.logger.log({
                    'message': 'Process_request отработал, response для очереди',
                    'response': str(response),
                    'request_id': response.get('request_id') if isinstance(response, dict) else None,
                    'status': response.get('status') if isinstance(response, dict) else None
                }, 'DEBUG') # *** ЛОГИРОВАНИЕ
                self.queue_manager.put_response(response)
                self.logger.log({
                    'message': 'Положен ответ в очередь',
                    'request_id': response.get('request_id') if isinstance(response, dict) else None,
                    'status': response.get('status') if isinstance(response, dict) else None
                }, 'DEBUG') # *** ЛОГИРОВАНИЕ
            except queue.Empty:
                continue
            except Exception as e:
                import traceback
                self.logger.log_error(f"{e} | {traceback.format_exc()}")

    def start(self):
        """Запустить агента."""
        if self._running:
            return
            
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop)
        self._worker_thread.start()
        self.logger.log({'message': ' Запущен AI Agent '}) # *** ЛОГИРОВАНИЕ

    def stop(self):
        """Остановить агента."""
        if not self._running:
            return
            
        self._running = False
        self.queue_manager.shutdown()
        
        if self._worker_thread:
            self._worker_thread.join()
            
        self.logger.log({'message': 'AI Agent остановлен'}) # *** ЛОГИРОВАНИЕ

    def _guess_image_mime_type(self, image_path: str) -> str:
        ext = os.path.splitext(image_path)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif ext == '.png':
            return 'image/png'
        else:
            return 'application/octet-stream'

    def submit_request(self, request: Dict[str, Any], image_path: str = None) -> None:
        import copy

        # Создаем копию запроса, чтобы не менять исходный словарь
        request_payload = copy.deepcopy(request)

        params = request_payload.get('params', {})

        if image_path:
            try:
                # Кодируем изображение в base64
                image_b64 = self.encode_image_to_base64(image_path)
                # Определяем MIME-тип изображения
                mime_type = self._guess_image_mime_type(image_path)

                # Добавляем в параметры поле images со структурой, ожидаемой API
                params['images'] = [{
                    "data": image_b64,
                    "type": mime_type
                }]

            except Exception as e:
                self.logger.log_error(f"Ошибка при кодировании изображения: {e}") # *** ЛОГИРОВАНИЕ
                raise

        # Записываем обновленные параметры в копию запроса
        request_payload['params'] = params

        # Логируем для отладки — проверить, что в params есть поле images с данными
        self.logger.log({
            "message": "Формируем запрос с параметрами",
            "request_id": request_payload.get('request_id'),
            "params": params
        }, "DEBUG") # *** ЛОГИРОВАНИЕ

        # Помещаем в очередь для асинхронной обработки
        self.queue_manager.put_request(request_payload)

        self.logger.log({
            "message": "Запрос помещён в очередь",
            "request_id": request_payload.get('request_id')
        }, "INFO") # *** ЛОГИРОВАНИЕ

    def get_response(self, request_id: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Асинхронно ожидает ответа из очереди ответов с заданным request_id,
        максимально timeout секунд. Если приходит ответ с другим request_id —
        кладёт ответ обратно в очередь и продолжает ждать.
        Если таймаут истекает — возбуждает исключение queue.Empty.
        """
        import queue

        while True:
            try:
                response = self.queue_manager.get_response(timeout=timeout)
            except queue.Empty:
                self.logger.log({
                    "message": f"Timeout ожидания ответа по request_id={request_id}"
                }, "WARNING") # *** ЛОГИРОВАНИЕ
                raise  # или выбросить свое исключение TimeoutError

            if response.get('request_id') == request_id:
                # Получен нужный ответ, возвращаем
                return response
            else:
                # Ответ не по тому request_id — кладём обратно и ждём дальше
                self.queue_manager.put_response(response)
                self.logger.log({
                    "message": "Ответ с другим request_id возвращён обратно в очередь",
                    "response_request_id": response.get('request_id'),
                    "expected_request_id": request_id
                }, "DEBUG") # *** ЛОГИРОВАНИЕ

