import json
import unittest
import time
import os
from core.agent import AIAgent
from queue import Empty

class TestAIAgent(unittest.TestCase):
    def setUp(self):
        # Используем временный файл для логов
        self.log_file = 'test_agent.log'
        self.agent = AIAgent(log_file=self.log_file)
        
        # Регистрируем тестовые API
        self.agent.register_api('test_echo', lambda x: x)
        self.agent.register_api('test_add', lambda a, b: a + b)
        
        self.agent.start()

    def tearDown(self):
        self.agent.stop()
        if os.path.exists(self.log_file):
            os.remove(self.log_file)

    def test_api_processing(self):
        # Тест синхронной обработки
        request = {
            'api': 'test_echo',
            'params': {'x': 'Hello, World!'},
            'request_id': 'test1'
        }
        
        request_id = self.agent.submit_request(request)
        response = self.agent.get_response(request_id)
        
        self.assertEqual(response['status'], 'success')
        self.assertEqual(response['data'], 'Hello, World!')
        self.assertEqual(response['request_id'], 'test1')

    def test_async_processing(self):
        # Тест асинхронной обработки нескольких запросов
        requests = [
            {'api': 'test_add', 'params': {'a': 2, 'b': 3}, 'request_id': 'add1'},
            {'api': 'test_add', 'params': {'a': 5, 'b': 7}, 'request_id': 'add2'},
            {'api': 'test_echo', 'params': {'x': 'test'}, 'request_id': 'echo1'}
        ]
        
        for req in requests:
            self.agent.submit_request(req)
        
        # Получаем ответы в произвольном порядке
        results = {}
        for _ in range(3):
            response = self.agent.get_response()
            results[response['request_id']] = response['data']
        
        self.assertEqual(results['add1'], 5)
        self.assertEqual(results['add2'], 12)
        self.assertEqual(results['echo1'], 'test')

    def test_error_handling(self):
        # Тест обработки ошибок
        request = {
            'api': 'nonexistent_api',
            'request_id': 'error_test'
        }
        
        self.agent.submit_request(request)
        response = self.agent.get_response('error_test')
        
        self.assertEqual(response['status'], 'error')
        self.assertIn("API 'nonexistent_api' not registered", response['error'])

    def test_logging(self):
        # Проверяем, что логи записываются
        request = {
            'api': 'test_echo',
            'params': {'x': 'log test'},
            'request_id': 'log_test'
        }
        
        self.agent.submit_request(request)
        self.agent.get_response('log_test')
        
        # Даем время на запись логов
        time.sleep(0.1)
        
        with open(self.log_file, 'r') as f:
            logs = [json.loads(line) for line in f.readlines()]
        
        self.assertTrue(any(log['type'] == 'REQUEST' for log in logs))
        self.assertTrue(any(log['type'] == 'RESPONSE' for log in logs))

if __name__ == '__main__':
    unittest.main()