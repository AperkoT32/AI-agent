# import requests       Работает только если платить денюжку ЗА API OpenAI
# import json 
# import time
# from typing import Dict, Any
# from core.logger import Logger

# class OpenAIHandler:
#     def __init__(self, config_path: str = 'config.json', log_file: str = 'openai.log'):
#         self.config = self.load_config(config_path)
#         self.logger = Logger(log_file)
#         self.session = requests.Session()
#         self.session.headers.update({
#             "Authorization": f"Bearer {self.config['api_key']}",
#             "Content-Type": "application/json"
#         })

#     def load_config(self, config_path: str) -> Dict[str, str]:
#         with open(config_path, 'r') as f:
#             return json.load(f)

#     def send_request(self, request: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
#         self.logger.log_request(request)
        
#         for attempt in range(max_retries):
#             try:
#                 response = self.session.post(
#                     f"{self.config['base_url']}/v1/chat/completions",
#                     json=request,
#                     timeout=self.config['timeout']
#                 )
#                 response.raise_for_status()
#                 result = response.json()
#                 self.logger.log_response(result)
#                 return result
#             except requests.exceptions.RequestException as e:
#                 self.logger.log_error(f"Attempt {attempt + 1} failed: {str(e)}")
#                 if attempt == max_retries - 1:
#                     raise
#                 time.sleep(2 ** attempt)  # Exponential backoff

#     def process_agent_request(self, agent_request: Dict[str, Any]) -> Dict[str, Any]:
#         openai_request = {
#             "model": self.config['model'],
#             "messages": [
#                 {"role": "system", "content": "You are a helpful assistant."},
#                 {"role": "user", "content": json.dumps(agent_request)}
#             ]
#         }
#         openai_response = self.send_request(openai_request)
#         return {
#             "status": "success",
#             "data": openai_response['choices'][0]['message']['content'],
#             "request_id": agent_request['request_id']
#         }