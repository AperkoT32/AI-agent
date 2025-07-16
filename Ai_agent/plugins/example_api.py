import time
import re
import base64
import requests
import mimetypes
import os
import queue
import importlib.util

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
                    self.conversation_history.append({
                        'role': 'user',
                        'content': user_question
                    })
                    
                    self.conversation_history.append({
                        'role': 'assistant',
                        'content': cleaned_response
                    })
                    
                    # Ограничиваем историю последними 10 сообщениями (5 пар вопрос-ответ)
                    if len(self.conversation_history) > 10:
                        self.conversation_history = self.conversation_history[-10:]
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
    
    def run(self):
        # Инициализация моделей
        if not self.initialize_models():
            print("Не удалось инициализировать модели. Завершение работы.")
            return
        
        print("Привет! Я Джейн — ваш ИИ-ассистент. Задайте вопрос или напишите «Пока», чтобы завершить.")
        print("Для работы с картинками напишите команду !import <название> + (.jpg/.png).")
        
        # Основной цикл диалога
        while True:
            user_question = input("Вы: ")
            if not self.process_user_input(user_question):
                break


# Обратной совместимость
def API_model(agent):
    assistant = JaneAssistant(agent)
    assistant.run()
        


