import time
import re
import base64
import requests
import mimetypes
import os
import queue
import importlib.util
import socket
import json

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")
MAX_RETRIES = 5
INITIAL_DELAY = 2
MAX_HISTORY_LENGTH = 10

def load_prompts():
    try:
        from config.prompts import JANE_SYSTEM_PROMPT, USER_INFO_TEMPLATE, IMAGE_CONTEXT_TEMPLATE
        return JANE_SYSTEM_PROMPT, USER_INFO_TEMPLATE, IMAGE_CONTEXT_TEMPLATE
    except ImportError:
        try:
            config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
            prompts_path = os.path.join(config_dir, "prompts.py")
            
            if os.path.exists(prompts_path):
                spec = importlib.util.spec_from_file_location("prompts", prompts_path)
                prompts_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(prompts_module)
                return (
                    prompts_module.JANE_SYSTEM_PROMPT,
                    prompts_module.USER_INFO_TEMPLATE,
                    prompts_module.IMAGE_CONTEXT_TEMPLATE
                )
            else:
                # Если файл не найден, используем значения по умолчанию
                return (
                    "Ты — ИИ-ассистент по имени Джейн. Всегда отвечай строго по запросу, лаконично и по существу.",
                    "\n\nИмя пользователя: {name}. Обращайся к пользователю по имени, когда это уместно.",
                    "\n\nВ предыдущем запросе было изображение '{filename}'. Контекст: {context}"
                )
        except Exception as e:
            print(f"Ошибка при загрузке промптов: {e}")
            # Значения по умолчанию в случае ошибки
            return (
                "Ты — ИИ-ассистент по имени Джейн. Всегда отвечай строго по запросу, лаконично и по существу.",
                "\n\nИмя пользователя: {name}. Обращайся к пользователю по имени, когда это уместно.",
                "\n\nВ предыдущем запросе было изображение '{filename}'. Контекст: {context}"
            )

def sanitize_input(user_input: str) -> str:
    # Удаляем все HTML-теги
    clean_text = re.sub(r'<.*?>', '', user_input)
    # Заменяем опасные символы на HTML-сущности
    clean_text = clean_text.replace('&', '&amp;')
    clean_text = clean_text.replace('<', '&lt;')
    clean_text = clean_text.replace('>', '&gt;')
    return clean_text

def is_assistant_name_question(question):
    patterns = [
        r'\bтвоё имя\b',
        r'\bтебя зовут\b',
        r'\bтебя называют\b',
        r'\bты называешься\b',
        r'\bкто ты\b',
        r'\bпредставься\b',
        r'\bтвоё название\b'
    ]
    return any(re.search(pattern, question.lower()) for pattern in patterns)


def clean_response(response_text):

    if '</think>' in response_text:
        response_text = response_text.split('</think>', 1)[1]

    # Удаляем префикс "Джейн:" в начале строк
    response_text = re.sub(r'^Джейн:\s*', '', response_text)

    lines = response_text.strip().splitlines()
    filtered_lines = []
    seen = set()

    # Если хотите использовать фильтр по ключевым словам, раскомментируйте и отредактируйте список
    # skip_words = ['пользователь', 'функция', 'в ответе', 'должен', 'следует', 'нужно', 'анализирую']

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Если нужен фильтр по ключевым словам, раскомментируйте:
        # if any(word in line.lower() for word in skip_words):
        #     continue
        if line not in seen:
            filtered_lines.append(line)
            seen.add(line)

    return '\n'.join(filtered_lines)

def is_meaningful_question(question: str) -> bool: # проверОчка на осмысленность запроса
    stripped = question.strip()
    if not stripped:
        return False  # пустая строка

    # Проверяем количество букв (ru/en)
    letters = re.findall(r'[а-яА-Яa-zA-Z]', stripped)
    if len(letters) < 3:
        return False

    # Проверяем длину
    if len(stripped) < 5:
        return False

    # Проверяем долю букв в строке (чтобы без Абв123)
    letter_ratio = len(letters) / len(stripped)
    if letter_ratio < 0.5:
        return False

    return True

def extract_final_answer(text):
    pattern_full = re.compile(r'<think>.*?</think>', re.DOTALL)
    match_full = pattern_full.search(text)
    if match_full:
        return text[match_full.end():].strip()

    # Если полного блока нет, ищем ТОЛЬКО ЗАКРЫВАЮЩИЙ тег </think> (НАКОНЕЦ ТО!!!)
    closing_tag = '</think>'
    if closing_tag in text:
        pos = text.find(closing_tag)
        return text[pos + len(closing_tag):].strip()
        
    return text.strip()

def get_base64_uri(image_path: str) -> str:
    ext = os.path.splitext(image_path)[1][1:].lower()  # например 'jpg', 'png'
    if not ext:
        ext = 'jpeg'  # по дефолту

    mime_type = mimetypes.types_map.get(f'.{ext}', 'image/jpeg')

    with open(image_path, "rb") as f:
        b64_str = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{b64_str}"

def select_models(models_data):
    text_model = None
    image_model = None
     
    text_model_preferences = ['gpt-4', 'gpt-3.5-turbo', 'claude']
    image_model_preferences = ['gpt-4-vision', 'claude-3-opus', 'claude-3-sonnet', 'gemini-pro-vision']
    
    for model in models_data:
        model_id = model.get('id', '').lower()
        
        if not text_model:
            for pref in text_model_preferences:
                if pref.lower() in model_id:
                    text_model = model['id']
                    break
        
        if not image_model:
            for pref in image_model_preferences:
                if pref.lower() in model_id:
                    image_model = model['id']
                    break
        
        if text_model and image_model:
            break
    
    if not text_model and models_data:
        text_model = models_data[0]['id']
    
    if not image_model:
        vision_keywords = ['vision', 'image', 'visual', 'multimodal']
        for model in models_data:
            model_id = model.get('id', '').lower()
            if any(keyword in model_id for keyword in vision_keywords):
                image_model = model['id']
                break
        
        if not image_model and text_model:
            image_model = text_model
    
    return text_model, image_model

class JaneAssistant:

    def __init__(self, agent):
        self.agent = agent
        self.current_image_path = None
        self.max_retries = MAX_RETRIES
        self.initial_delay = INITIAL_DELAY
        
        # Переменные для хранения контекста изображений
        self.last_image_context = None
        self.last_image_filename = None
        self.had_image_in_last_request = False
        
        self.conversation_history = []
        self.user_info = {}
        
        # Модели для текста и изображений
        self.model_name_for_text = None
        self.model_name_for_image = None

        self.system_prompt, self.user_info_template, self.image_context_template = load_prompts()

            # Добавляем периодическую очистку памяти
        self.request_counter = 0
        self.memory_cleanup_interval = 10  # Очистка каждые 10 запросов

    def get_system_prompt(self):
        prompt = self.system_prompt
        
        if 'name' in self.user_info:
            prompt += self.user_info_template.format(name=self.user_info['name'])
        
        if self.had_image_in_last_request and self.last_image_context and self.last_image_filename:
            prompt += self.image_context_template.format(
                filename=self.last_image_filename,
                context=self.last_image_context
            )
        
        return prompt
    
    def initialize_models(self):
        """Получает список доступных моделей и выбирает подходящие для текста и изображений."""
        iointel_models = {
            'api': 'iointelligence',
            'endpoint': 'models',
            'method': 'GET',
            'params': {},
            'request_id': f'req_iointel_models_{int(time.time()*1000)}'
        }

        # Запрашиваем модели с retry
        for attempt in range(self.max_retries):
            iointel_models['request_id'] = f'req_iointel_models_{int(time.time()*1000)}'
            self.agent.submit_request(iointel_models)
            try:
                response_models = self.agent.get_response(iointel_models['request_id'], timeout=60)
            except queue.Empty:
                print(f"Попытка {attempt + 1}: Время ожидания ответа модели истекло.")
                if attempt == self.max_retries - 1:
                    print("Не удалось получить список моделей.")
                    return False
                delay = min(self.initial_delay * (2 ** attempt), 30)
                time.sleep(delay)
                continue

            if response_models.get('status') == 'error' and '429' in response_models.get('error',''):
                delay = min(self.initial_delay * (2 ** attempt), 30)
                print(f"Попытка {attempt + 1}: Ошибка 429, повтор через {delay} сек")
                time.sleep(delay)
                continue

            if response_models.get('status') == 'success':
                models_data = response_models['data'].get('data', [])
                model_ids = [m['id'] for m in models_data if 'id' in m]

                if not models_data:
                    print("Не получены данные о моделях")
                    return False
                
                

                # Автоматический выбор моделей
                auto_text_model, auto_image_model = select_models(models_data)

                # Ручной выбор закоменчен
                manual_text_model = model_ids[0] if len(model_ids) > 0 else None
                manual_image_model = model_ids[4] if len(model_ids) > 4 else None

                # Приоритет 
                self.model_name_for_text = auto_text_model
                self.model_name_for_image = auto_image_model

                #  ручного выбора
                # if manual_text_model:
                #     self.model_name_for_text = manual_text_model
                # if manual_image_model:
                #     self.model_name_for_image = manual_image_model

                if not self.model_name_for_text:
                    print("Не удалось выбрать модель для текста")
                    return False
                
                if not self.model_name_for_image:
                    print("Не удалось выбрать модель для изображений, будет использована текстовая модель")
                    self.model_name_for_image = self.model_name_for_text

                #  отладки
                # print(f"Модель для текста: {self.model_name_for_text}")
                # print(f"Модель для изображений: {self.model_name_for_image}")


                return True
            else:
                print(f"Ошибка получения списка моделей: {response_models.get('error', 'неизвестно')}")
                return False
        
        return False
    
    def process_user_input(self, user_question):
        user_question = sanitize_input(user_question)
        if user_question.strip().lower() in ['пока', 'пока, джейн', 'до свидания', 'выход', 'exit']:
            print("До встречи!")
            return False
        
        # Проверяем, представляется ли пользователь
        name_patterns = [
            r'меня зовут (\w+)',
            r'я (\w+)',
            r'моё имя (\w+)',
            r'мое имя (\w+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, user_question.lower())
            if match:
                self.user_info['name'] = match.group(1).capitalize()
                break
        
        if is_assistant_name_question(user_question):
            print("Меня зовут Джейн. Я ИИ-ассистент, готова помочь вам с различными вопросами.")
            return True
        
        if not is_meaningful_question(user_question):
            print("Мне сложно понять ваш запрос. Можете, пожалуйста, уточнить или переформулировать? "
                  "Я с радостью помогу!")
            return True
        
        # Обработка команды импорта изображения
        if user_question.startswith('!import '):
            filename = user_question[len('!import '):].strip()
            image_path = os.path.join(IMAGES_DIR, filename)
            if os.path.isfile(image_path):
                self.current_image_path = image_path
                self.last_image_filename = filename
                print(f"Изображение '{filename}' загружено и будет использовано в следующем запросе.")
            else:
                print(f"Файл '{filename}' не найден в папке '{IMAGES_DIR}'. Проверьте имя и попробуйте снова.")
            return True
        
        # Обработка обычного запроса
        self.handle_chat_request(user_question)
        return True
    
    def handle_chat_request(self, user_question):

        if not self.is_agent_active():
            print("Ошибка: Агент не активен")
            return "Извините, сервис временно недоступен."
        
        # Выбираем модель в зависимости от того, есть ли изображение
        model_name = self.model_name_for_image if self.current_image_path else self.model_name_for_text
        
        # Проверяем, связан ли текущий запрос с предыдущим изображением
        is_image_related_question = False
        if self.had_image_in_last_request and not self.current_image_path:
            image_related_keywords = ['изображение', 'картинка', 'фото', 'на фото', 'на изображении', 
                                     'на картинке', 'на снимке', 'это', 'этот', 'эта', 'эти']
            is_image_related_question = any(keyword in user_question.lower() for keyword in image_related_keywords)
        
        max_retries_chat = 5
        initial_delay_chat = 2
        
        for attempt in range(max_retries_chat):
            request_id = f'req_iointel_chat_{int(time.time() * 1000)}'
            
            # Подготовка контента запроса
            if self.current_image_path:
                base64_image_uri = get_base64_uri(self.current_image_path)
                # Формируем content как список с текстом и изображением
                user_content = [
                    {"type": "text", "text": user_question},
                    {"type": "image_url", "image_url": {"url": base64_image_uri}}
                ]
            else:
                user_content = user_question
            
            system_prompt = self.get_system_prompt()
            
            # Формируем запрос к API
            chat_request = {
                'api': 'iointelligence',
                'endpoint': 'chat/completions',
                'method': 'POST',
                'params': {
                    'model': model_name,
                    'messages': [
                        {
                            'role': 'system',
                            'content': system_prompt
                        }
                    ] + (self.conversation_history[-10:] if self.conversation_history else []) + [
                        {
                            'role': 'user',
                            'content': user_content
                        }
                    ]
                },
                'request_id': request_id
            }
            
            self.agent.submit_request(chat_request)
            
            try:
                chat_response = self.agent.get_response(request_id, timeout=30)
            except queue.Empty:
                print(f"Попытка {attempt + 1}: Время ожидания ответа истекло.")
                if attempt == max_retries_chat - 1:
                    print("Слишком много попыток. Ответ не получен.")
                    break
                delay = min(initial_delay_chat * (2 ** attempt), 30)
                time.sleep(delay)
                continue
            
            if chat_response.get('status') == 'error' and '429' in chat_response.get('error', ''):
                delay = min(initial_delay_chat * (2 ** attempt), 30)
                print(f"Попытка {attempt + 1}: Ошибка 429, повтор через {delay} сек")
                time.sleep(delay)
                continue
            
            if chat_response.get('status') == 'success':
                choices = chat_response['data'].get('choices', [])
                if choices and 'message' in choices[0]:
                    text = choices[0]['message']['content']
                    text_no_think = extract_final_answer(text)
                    cleaned_response = clean_response(text_no_think)
                    print('Джейн:', cleaned_response)
            
                    # Сохраняем контекст, если был запрос с изображением
                    if self.current_image_path:
                        self.last_image_context = cleaned_response
                        self.had_image_in_last_request = True
            
                    # Обновляем историю диалога
                    # Сначала проверяем, не превышен ли лимит
                    if len(self.conversation_history) >= MAX_HISTORY_LENGTH:
                        # Удаляем старые сообщения, чтобы освободить место для новых
                        self.conversation_history = self.conversation_history[-(MAX_HISTORY_LENGTH-2):]
                        print(f"[DEBUG] История сокращена перед добавлением новых сообщений")
            
                    self.conversation_history.append({
                        'role': 'user',
                        'content': user_question
                    })
            
                    self.conversation_history.append({
                        'role': 'assistant',
                        'content': cleaned_response
                    })

                    print(f"[DEBUG] Длина истории после добавления: {len(self.conversation_history)}")
            
                    # Очищаем большие объекты из памяти
                    if self.current_image_path:
                        # Если изображение было обработано, очищаем base64_image_uri
                        base64_image_uri = None
                        # Запускаем сборщик мусора для освобождения памяти
                        import gc
                        gc.collect()
                    # Ограничиваем историю последними 10 сообщениями (5 пар вопрос-ответ)
                    if len(self.conversation_history) > 10:
                        self.conversation_history = self.conversation_history[-10:]
                        print(f"[DEBUG] История ограничена до 10 сообщений")

                    print(f"[DEBUG] Длина истории после ограничения: {len(self.conversation_history)}")
                else:
                    print("Неверный ответ модели:", chat_response)
                break
            else:
                print("Ошибка ответа:", chat_response.get('error', 'Неизвестно'))
                break
        

        if self.current_image_path:
            self.current_image_path = None
        elif not is_image_related_question:
            self.had_image_in_last_request = False
            self.last_image_context = None
            self.last_image_filename = None

    def is_agent_active(self):
        try:
            return self.agent._running and self.agent.queue_manager.active
        except:
            return False
        
    def cleanup_memory(self):
        import gc
    
        # Ограничиваем историю
        if len(self.conversation_history) > MAX_HISTORY_LENGTH:
            self.conversation_history = self.conversation_history[-MAX_HISTORY_LENGTH:]
    
        gc.collect()
    
        print("[DEBUG] Выполнена очистка памяти")
        
    def ask(self, user_question):
        print(f"[DEBUG] Получен вопрос: {user_question}")

        # Периодическая очистка памяти
        self.request_counter += 1
        if self.request_counter % self.memory_cleanup_interval == 0:
            self.cleanup_memory()

        if not user_question or user_question.strip() == '':
            print("[DEBUG] Получено пустое сообщение")
            return "Пожалуйста, введите ваш вопрос."
    
        if not self.is_agent_active():
            print("Ошибка: Агент не активен")
            return "Извините, сервис временно недоступен."

        history_length_before = len(self.conversation_history)
        print(f"[DEBUG] Длина истории до обработки: {history_length_before}")

        # Ограничиваем историю перед обработкой нового запроса
        if len(self.conversation_history) > MAX_HISTORY_LENGTH:
            self.conversation_history = self.conversation_history[-MAX_HISTORY_LENGTH:]
            print(f"[DEBUG] История предварительно ограничена до {MAX_HISTORY_LENGTH} сообщений")
    
        self.handle_chat_request(user_question)

        history_length_after = len(self.conversation_history)
        print(f"[DEBUG] Длина истории после обработки: {history_length_after}")

        # Строгое ограничение истории после обработки
        if len(self.conversation_history) > MAX_HISTORY_LENGTH:
            self.conversation_history = self.conversation_history[-MAX_HISTORY_LENGTH:]
            print(f"[DEBUG] История окончательно ограничена до {MAX_HISTORY_LENGTH} сообщений")
            history_length_after = len(self.conversation_history)
            print(f"[DEBUG] Обновленная длина истории: {history_length_after}")
    
        if history_length_after >= history_length_before:

            # Получаем последний ответ ассистента
            for i in range(len(self.conversation_history) - 1, -1, -1):
                if self.conversation_history[i]['role'] == 'assistant':
                    response = self.conversation_history[i]['content']
                    print(f"[DEBUG] Возвращаем ответ: {response[:50]}...")
                    return response
    
        print("[DEBUG] Не удалось получить ответ")
        return "Извините, не удалось получить ответ."
    def run(self):
        # Инициализация моделей
        if not self.initialize_models():
            print("Не удалось инициализировать модели. Завершение работы.")
            return

        HOST = '127.0.0.1'
        PORT = 5050

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((HOST, PORT))
            server_socket.listen(1)
            print(f"[Jane Assistant] Слушает на {HOST}:{PORT}")

            while True:
                try:
                    if not self.is_agent_active():
                        print("Агент не активен. Завершение работы сервера.")
                        break
            
                    server_socket.settimeout(1.0)
                    try:
                        conn, addr = server_socket.accept()
                    except socket.timeout:
                        continue
                
                    print(f"[DEBUG] Получено соединение от {addr}")
                    with conn:
                        data = conn.recv(4096)
                        if not data:
                            print("[DEBUG] Получены пустые данные")
                            continue
                        try:
                            print(f"[DEBUG] Получены данные: {data}")
                            request = json.loads(data.decode())
                            print(f"[DEBUG] Декодированный запрос: {request}")
                            user_message = request.get("message", "")
                            print(f"[DEBUG] Сообщение пользователя: {user_message}")

                            if not user_message:
                                print("[DEBUG] Пустое сообщение")
                                response = {"error": "Пустое сообщение"}
                            else:
                                # Проверяем, активен ли агент
                                if not self.is_agent_active():
                                    print("Ошибка: Агент не активен")
                                    response = {"error": "Сервис временно недоступен"}
                                else:
                                    # Санитизация входящего сообщения
                                    sanitized_message = sanitize_input(user_message)
                                    print(f"[DEBUG] Санитизированное сообщение: {sanitized_message}")
                                
                                    print(f"[DEBUG] Вызов метода ask с сообщением: {sanitized_message}")
                                    agent_response = self.ask(sanitized_message)
                                    print(f"[DEBUG] Получен ответ от ask: {agent_response[:50]}...")
                                    response = {"response": agent_response}

                            print(f"[DEBUG] Отправка ответа: {response}")
                            conn.sendall(json.dumps(response).encode())
                            print("[DEBUG] Ответ отправлен")
                        except Exception as e:
                            print(f"[DEBUG] Исключение при обработке запроса: {str(e)}")
                            import traceback
                            print(traceback.format_exc())
                            response = {"error": str(e)}
                            conn.sendall(json.dumps(response).encode())
                except Exception as e:
                    print(f"Ошибка в основном цикле сервера: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
                    # Если произошла критическая ошибка, выходим из цикла
                    if not self.is_agent_active():
                        break


# Обратной совместимость
def API_model(agent):
    try:
        jane = JaneAssistant(agent)
        jane.run()
    except Exception as e:
        print(f"Ошибка в API_model: {str(e)}")
        import traceback
        print(traceback.format_exc())


