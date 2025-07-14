import queue
import threading
from typing import Dict, Any
from .queue_manager import QueueManager
from .api_handler import APIHandler
from .logger import Logger
from.iointell_handler import APIHandler  
#from .openai_handler import OpenAIHandler

class AIAgent:
    """
    Основной класс ИИ-агента.
    Управляет очередями запросов/ответов, обработкой API и логированием.
    """
    
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


    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Загружает конфигурацию из JSON файла."""
        import json
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            self.logger.log_error(f"json не найден: {config_path}")
            return {}
        except json.JSONDecodeError:
            self.logger.log_error(f"неправельный json формат: {config_path}")
            return {}

    def register_api(self, name: str, handler: callable):
        """Регистрация API обработчика."""
        self.api_handler.register_api(name, handler)
        self.logger.log({
            'message': 'Зарегистрированный обработчик API',
            'api_name': name
        })

    def register_api_module(self, module_path: str):
        """Регистрация модуля с API обработчиками."""
        self.api_handler.register_api_module(module_path)
        self.logger.log({
            'message': 'Зарегистрированный модуль API',
            'module_path': module_path
        })

    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработать запрос.
        Возвращает словарь с результатом или ошибкой.
        """
        try:
            self.logger.log_request(request)

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

            self.logger.log_response(response)
            return response

        except Exception as e:
            error_response = {
                'status': 'error',
                'request_id': request.get('request_id'),
                'error': str(e)
            }
            self.logger.log_error(str(e), {'request': request})
            return error_response

    def _worker_loop(self):
        """Основной цикл обработки запросов."""
        while self._running:
            try:
                request = self.queue_manager.get_request(timeout=0.1)
                response = self.process_request(request)
                self.queue_manager.put_response(response)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.log_error(str(e))

    def start(self):
        """Запустить агента."""
        if self._running:
            return
            
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop)
        self._worker_thread.start()
        self.logger.log({'message': ' Запущен AI Agent '})

    def stop(self):
        """Остановить агента."""
        if not self._running:
            return
            
        self._running = False
        self.queue_manager.shutdown()
        
        if self._worker_thread:
            self._worker_thread.join()
            
        self.logger.log({'message': 'AI Agent остановлен'})

    def submit_request(self, request: Dict[str, Any]) -> str:
        """
        Отправить запрос на обработку.
        Возвращает request_id для отслеживания ответа.
        """
        if 'request_id' not in request:
            request['request_id'] = str(hash(frozenset(request.items())))
            
        self.queue_manager.put_request(request)
        return request['request_id']

    def get_response(self, request_id: str = None, block=True, timeout=None) -> Dict[str, Any]:
        """
        Получить ответ из очереди.
        Если request_id указан, будет возвращен первый соответствующий ответ.
        """
        response = self.queue_manager.get_response(block, timeout)
        
        if request_id and response.get('request_id') != request_id:
            # Если нужен конкретный ответ, но получен другой,
            # возвращаем его обратно в очередь и продолжаем ждать
            self.queue_manager.put_response(response)
            return self.get_response(request_id, block, timeout)
            
        return response