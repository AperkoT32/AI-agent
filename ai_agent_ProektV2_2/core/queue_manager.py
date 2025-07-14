import queue
from typing import Any, Dict

class QueueManager:
    """
    Менеджер очередей для обработки запросов и ответов агента.
    Поддерживает отдельные очереди для входящих запросов и исходящих ответов.
    """
    
    def __init__(self):
        self.request_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.active = True

    def put_request(self, item: Dict[str, Any]):
        """Добавить запрос в очередь обработки."""
        if self.active:
            self.request_queue.put(item)
        else:
            raise RuntimeError("QueueManager is not active")

    def get_request(self, block=True, timeout=None) -> Dict[str, Any]:
        """Получить следующий запрос из очереди."""
        return self.request_queue.get(block, timeout)

    def put_response(self, item: Dict[str, Any]):
        """Добавить ответ в очередь результатов."""
        if self.active:
            self.response_queue.put(item)
        else:
            raise RuntimeError("QueueManager is not active")

    def get_response(self, block=True, timeout=None) -> Dict[str, Any]:
        """Получить следующий ответ из очереди."""
        return self.response_queue.get(block, timeout)

    def shutdown(self):
        """Остановить менеджер очередей."""
        self.active = False
        # Очищаем очереди для разблокировки ожидающих потоков
        while not self.request_queue.empty():
            self.request_queue.get()
        while not self.response_queue.empty():
            self.response_queue.get()