from typing import Dict, Callable, Any
import importlib
import inspect

class APIHandler:
    """
    Обработчик для регистрации и управления внешними API.
    Поддерживает динамическую загрузку API обработчиков.
    """
    
    def __init__(self):
        self._apis: Dict[str, Callable] = {}

    def register_api(self, name: str, handler: Callable):
        """Регистрация нового API обработчика."""
        if not inspect.isfunction(handler) and not inspect.ismethod(handler):
            raise ValueError("Обработчик должен быть функцией или методом")
        self._apis[name] = handler

    def register_api_module(self, module_path: str):
        """Регистрация всех API из модуля."""
        module = importlib.import_module(module_path)
        
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and name.startswith('handle_'):
                api_name = name[7:]  # Удаляем 'handle_' префикс
                self.register_api(api_name, obj)

    def get_api(self, name: str) -> Callable:
        """Получить обработчик API по имени."""
        if name not in self._apis:
            raise KeyError(f"API '{name}' не зарегестрировано")
        return self._apis[name]

    def list_apis(self) -> Dict[str, Any]:
        """Получить список всех зарегистрированных API."""
        return {name: str(handler) for name, handler in self._apis.items()}