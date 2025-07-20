# import unittest
# from unittest.mock import patch, MagicMock                                                                   Только для тестирования, не использовать в реальной работе 
# from core.openai_handler import OpenAIHandler

# class TestOpenAIHandler(unittest.TestCase):
#     def setUp(self):
#         self.handler = OpenAIHandler('test_config.json', 'test_openai.log')

#     @patch('requests.Session.post')
#     def test_send_request(self, mock_post):
#         mock_response = MagicMock()
#         mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
#         mock_post.return_value = mock_response

#         request = {
#             "model": "gpt-3.5-turbo",
#             "messages": [{"role": "user", "content": "Hello"}]
#         }
#         response = self.handler.send_request(request)

#         self.assertEqual(response, {"choices": [{"message": {"content": "Test response"}}]})
#         mock_post.assert_called_once()

#     @patch('requests.Session.post')
#     def test_process_agent_request(self, mock_post):
#         mock_response = MagicMock()
#         mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
#         mock_post.return_value = mock_response

#         agent_request = {
#             "api": "openai",
#             "params": {"prompt": "Tell me a joke"},
#             "request_id": "test123"
#         }
#         response = self.handler.process_agent_request(agent_request)

#         self.assertEqual(response, {
#             "status": "success",
#             "data": "Test response",
#             "request_id": "test123"
#         })
#         mock_post.assert_called_once()

# if __name__ == '__main__':
#     unittest.main()