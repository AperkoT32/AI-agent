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
import sqlite3
import spacy
import threading
import config.config_setting as config_setting
from plugins.db_manager import DatabaseManager
from plugins.web_search import search_web
from typing import Optional
from transformers import pipeline


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
                return (
                    "Ты — ИИ-ассистент по имени Джейн. Всегда отвечай строго по запросу, лаконично и по существу.",
                    "\n\nИмя пользователя: {name}. Обращайся к пользователю по имени, когда это уместно.",
                    "\n\nВ предыдущем запросе было изображение '{filename}'. Контекст: {context}"
                )
        except Exception as e:
            print(f"Ошибка при загрузке промптов: {e}")
            return (
                "Ты — ИИ-ассистент по имени Джейн. Всегда отвечай строго по запросу, лаконично и по существу.",
                "\n\nИмя пользователя: {name}. Обращайся к пользователю по имени, когда это уместно.",
                "\n\nВ предыдущем запросе было изображение '{filename}'. Контекст: {context}"
            )
def sanitize_input(user_input: str) -> str:
    clean_text = re.sub(r'<.*?>', '', user_input)
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

    response_text = re.sub(r'^Джейн:\s*', '', response_text)

    lines = response_text.strip().splitlines()
    filtered_lines = []
    seen = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line not in seen:
            filtered_lines.append(line)
            seen.add(line)

    return '\n'.join(filtered_lines)

def is_meaningful_question(question: str) -> bool: 
    stripped = question.strip()
    if not stripped:
        return False 

    letters = re.findall(r'[а-яА-Яa-zA-Z]', stripped)
    if len(letters) < 3:
        return False

    if len(stripped) < 5:
        return False

    letter_ratio = len(letters) / len(stripped)
    if letter_ratio < 0.5:
        return False

    return True

def extract_final_answer(text):
    pattern_full = re.compile(r'> .*?', re.DOTALL)
    match_full = pattern_full.search(text)
    if match_full:
        return text[match_full.end():].strip()

    closing_tag = '</think>'
    if closing_tag in text:
        pos = text.find(closing_tag)
        return text[pos + len(closing_tag):].strip()
        
    return text.strip()

def get_base64_uri(image_path: str) -> str:

    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Файл '{image_path}' не найден. Проверьте путь и повторите попытку.")

    ext = os.path.splitext(image_path)[1][1:].lower() 
    if not ext:
        ext = 'jpeg'  

    mime_type = mimetypes.types_map.get(f'.{ext}', 'image/jpeg')

    try:
        with open(image_path, "rb") as f:
            b64_str = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        raise IOError(f"Ошибка при чтении файла '{image_path}': {str(e)}")

    return f"data:{mime_type};base64,{b64_str}"

def select_models(models_data):
    text_model = None
    image_model = None
    text_model_preferences = config_setting.TEXT_MODEL_PREFERENCES
    image_model_preferences = config_setting.IMAGE_MODEL_PREFERENCES
    
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

    def __init__(self, agent, server_ready_event: Optional[threading.Event] = None):
        self.agent = agent
        self.server_ready_event = server_ready_event
        self.current_image_path = None
        self.max_retries = config_setting.MAX_RETRIES
        self.initial_delay = config_setting.INITIAL_DELAY
        self.last_image_context = None
        self.last_image_filename = None
        self.had_image_in_last_request = False
        self.user_info = {}
        self.db_manager = DatabaseManager() 
        self.model_name_for_text = None
        self.model_name_for_image = None
        self.system_prompt, self.user_info_template, self.image_context_template = load_prompts()
        self.request_counter = 0
        self.memory_cleanup_interval = 10

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
        print("[DEBUG] Начало инициализации моделей...")
        # Инициализация NLP моделей
        if not self.initialize_nlp_models():
            print("[DEBUG] Ошибка инициализации NLP моделей")
            return False

        iointel_models = {
            'api': 'iointelligence',
            'endpoint': 'models',
            'method': 'GET',
            'params': {},
            'request_id': f'req_iointel_models_{int(time.time()*1000)}'
        }

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
                
                auto_text_model, auto_image_model = select_models(models_data)

                self.model_name_for_text = auto_text_model
                self.model_name_for_image = auto_image_model

                if not self.model_name_for_text:
                    print("Не удалось выбрать модель для текста")
                    return False
                
                if not self.model_name_for_image:
                    print("Не удалось выбрать модель для изображений, будет использована текстовая модель")
                    self.model_name_for_image = self.model_name_for_text

                print(f"Модель для текста: {self.model_name_for_text}")
                return True
            else:
                print(f"Ошибка получения списка моделей: {response_models.get('error', 'неизвестно')}")
                return False
        
        if not self.initialize_nlp_models():
            print("Не удалось инициализировать NLP модели.")
            return False
        return True
    
    def initialize_nlp_models(self):
        try:
            print("[DEBUG] Начало загрузки NLP моделей...")
            print("[DEBUG] Загрузка spaCy модели ru_core_news_lg...")
            self.nlp = spacy.load("ru_core_news_lg")
            
            ruler = self.nlp.add_pipe("entity_ruler", before="ner")
            patterns = [
                {"label": "DATE", "pattern": [{"SHAPE": "d"}, {"LOWER": {"IN": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]}}, {"SHAPE": "dddd"}]},
                {"label": "DATE", "pattern": [{"SHAPE": "dd"}, {"LOWER": {"IN": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]}}, {"SHAPE": "dddd"}]},
                {"label": "DATE", "pattern": [{"SHAPE": "d"}, {"LOWER": {"IN": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]}}]},
                {"label": "DATE", "pattern": [{"SHAPE": "dd"}, {"LOWER": {"IN": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]}}]},
                
                {"label": "MONEY", "pattern": [{"LIKE_NUM": True}, {"LOWER": {"IN": ["рублей", "рубля", "руб", "₽"]}}]},
                {"label": "MONEY", "pattern": [{"LIKE_NUM": True}, {"LOWER": "миллион"}, {"LOWER": {"IN": ["рублей", "рубля", "руб", "₽"]}}]},
                {"label": "MONEY", "pattern": [{"LIKE_NUM": True}, {"LOWER": "миллиард"}, {"LOWER": {"IN": ["рублей", "рубля", "руб", "₽"]}}]},
                
                {"label": "ROLE", "pattern": [{"LOWER": "президент"}]},
                {"label": "ROLE", "pattern": [{"LOWER": "министр"}]},
                {"label": "ROLE", "pattern": [{"LOWER": "директор"}]},
                {"label": "ROLE", "pattern": [{"LOWER": "генеральный"}, {"LOWER": "директор"}]},
                
                {"label": "GPE", "pattern": "Россия"},
                {"label": "GPE", "pattern": "России"},
                {"label": "GPE", "pattern": "РФ"},
                {"label": "GPE", "pattern": "Казань"},
                {"label": "GPE", "pattern": "Казани"},
                {"label": "GPE", "pattern": "Москва"},
                {"label": "GPE", "pattern": "Москвы"},
                {"label": "GPE", "pattern": "Москве"},
                {"label": "GPE", "pattern": "Санкт-Петербург"},
                {"label": "GPE", "pattern": "Санкт-Петербурге"},
                {"label": "GPE", "pattern": "Петербург"},
                {"label": "GPE", "pattern": "Петербурге"}
            ]
            ruler.add_patterns(patterns)
            print("[DEBUG] spaCy модель успешно загружена и настроена")
            print("[DEBUG] Инициализация question-answering pipeline...")
            self.qa_pipeline = pipeline("question-answering", model="distilbert-base-cased-distilled-squad")
            print("[DEBUG] Pipeline успешно инициализирован")
            print("[DEBUG] Все NLP модели успешно загружены")
            return True
        except Exception as e:
            print(f"[DEBUG] Ошибка при инициализации NLP моделей: {str(e)}")
            print(f"[DEBUG] Тип ошибки: {type(e).__name__}")
            import traceback
            print("[DEBUG] Стек вызовов:")
            print(traceback.format_exc())
            return False
    def handle_chat_request(self, user_question, chat_id: Optional[str] = None):
        if not self.is_agent_active():
            print("Ошибка: Агент не активен")
            return "Извините, сервис временно недоступен."
    
        model_name = self.model_name_for_image if self.current_image_path else self.model_name_for_text
    
        is_image_related_question = False
        if self.had_image_in_last_request and not self.current_image_path:
            image_related_keywords = ['изображение', 'картинка', 'фото', 'на фото', 'на изображении', 
                                    'на картинке', 'на снимке', 'это', 'этот', 'эта', 'эти']
            is_image_related_question = any(keyword in user_question.lower() for keyword in image_related_keywords)
    
        max_retries_chat = 5
        user_content = ""  
        response_text = None  
    
        for attempt in range(max_retries_chat):
            try:
                request_id = f'req_iointel_chat_{int(time.time() * 1000)}'
            
                if self.current_image_path:
                    try:
                        base64_image_uri = get_base64_uri(self.current_image_path)
                        user_content = [
                            {"type": "text", "text": user_question},
                            {"type": "image_url", "image_url": {"url": base64_image_uri}}
                        ]
                    except Exception as e:
                        return f"Ошибка при обработке изображения: {str(e)}"
                else:
                    user_content = user_question
            
                system_prompt = self.get_system_prompt()

                current_chat_history = []

                if chat_id:
                    current_chat_history = self.db_manager.load_chat_history(chat_id)     

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
                        ] + (current_chat_history[-config_setting.MAX_HISTORY_LENGTH:] if current_chat_history else []) + [ 
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
                    delay = min(self.initial_delay * (2 ** attempt), 30)
                    time.sleep(delay)
                    continue
                if chat_response.get('status') == 'error' and '429' in chat_response.get('error', ''):
                    delay = min(self.initial_delay * (2 ** attempt), 30)
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
                    
                        response_text = cleaned_response  
            
                        if self.current_image_path:
                            self.last_image_context = cleaned_response
                            self.had_image_in_last_request = True
            
                        if self.current_image_path:
                            base64_image_uri = None
                            import gc
                            gc.collect()
                    else:
                        print("Неверный ответ модели:", chat_response)
                        response_text = "Получен неверный ответ от модели"
                    break
                else:
                    print("Ошибка ответа:", chat_response.get('error', 'Неизвестно'))
                    response_text = f"Ошибка API: {chat_response.get('error', 'Неизвестно')}"
                    break
                
            except Exception as e:
                response_text = f"Ошибка при обработке запроса: {str(e)}"
                break
    
        if self.current_image_path:
            self.current_image_path = None
        elif not is_image_related_question:
            self.had_image_in_last_request = False
            self.last_image_context = None
            self.last_image_filename = None
    
        return response_text if response_text else "Извините, не удалось получить ответ."

    def is_agent_active(self):
        try:
            return self.agent._running and self.agent.queue_manager.active
        except:
            return False
    
    def cleanup_memory(self):
        import gc
        gc.collect()

    def ask(self, user_question, chat_id: Optional[str] = None):
        self.request_counter += 1
        if self.request_counter % self.memory_cleanup_interval == 0:
            self.cleanup_memory()

        if not user_question or user_question.strip() == '':
            return "Пожалуйста, введите ваш вопрос."

        if not self.is_agent_active():
            print("Ошибка: Агент не активен")
            return "Извините, сервис временно недоступен."
        
        user_question_lower = user_question.lower()

        mark_done_match = re.search(r'(отметь|выполни|сделай)\s+(?:задачу|пункт)?\s*(?:под номером)?\s*(\d+)\s+(выполненной|сделанной)', user_question_lower)
        if mark_done_match:
            try:
                index = int(mark_done_match.group(2))
                return self.db_manager.update_todo_by_ui_index(index, True)
            except ValueError:
                return "Неверный номер задачи. Пожалуйста, укажите число."
            
        doc = self.nlp(user_question)
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        print(f"Обнаруженные сущности: {entities}")
        
        print("\n[DEBUG] Подробная информация о сущностях:")
        for ent in doc.ents:
            print(f"- Сущность: {ent.text}")
            print(f"  Тип: {ent.label_}")
            print(f"  Описание: {spacy.explain(ent.label_)}")
            print(f"  Начальная позиция: {ent.start_char}")
            print(f"  Конечная позиция: {ent.end_char}")

        if "вопрос" in user_question.lower():
            answer = self.qa_pipeline(question=user_question, context="Ваш контекст здесь")
            return answer["answer"]

        mark_undone_match = re.search(r'(отметь|сделай)\s+(?:задачу|пункт)?\s*(?:под номером)?\s*(\d+)\s+(невыполненной|не\s+сделанной)', user_question_lower)
        if mark_undone_match:
            try:
                index = int(mark_undone_match.group(2))
                return self.db_manager.update_todo_by_ui_index(index, False)
            except ValueError:
                return "Неверный номер задачи. Пожалуйста, укажите число."

        mark_reading_match = re.search(r'(отметь|пометь)\s+(?:задачу|пункт)?\s*(?:под номером)?\s*(\d+)\s+(нужно\s+почитать|для\s+чтения)', user_question_lower)
        if mark_reading_match:
            try:
                index = int(mark_reading_match.group(2))
                return self.db_manager.mark_for_reading_by_ui_index(index)
            except ValueError:
                return "Неверный номер задачи. Пожалуйста, укажите число."


        add_task_match = re.search(r'(добавь|добавить|создай|создать)\s+(?:задачу|в список|в память|в туду)\s+(.+)', user_question_lower)
        if add_task_match:
            task = add_task_match.group(2).strip()
            return self.db_manager.add_todo(task)

        delete_task_match_by_id = re.search(r'(удали|удалить|сотри|стереть)\s+(?:задачу|пункт)?\s*(?:под номером)?\s*(\d+)', user_question_lower)
        delete_task_match_by_name = re.search(r'(удали|удалить|сотри|стереть)\s+(?:задачу|пункт)?\s+(.+)', user_question_lower)

        if delete_task_match_by_id:
            try:
                index = int(delete_task_match_by_id.group(2))
                return self.db_manager.delete_todo_by_ui_index(index)
            except ValueError:
                return "Неверный номер задачи. Пожалуйста, укажите число."


        add_task_match = re.search(r'(добавь|добавить|создай|создать)\s+(?:задачу|в список|в память|в туду)\s+(.+)', user_question_lower)
        if add_task_match:
            task = add_task_match.group(2).strip()
            return self.db_manager.add_todo(task)
        
        delete_task_match_by_id = re.search(r'(удали|удалить|сотри|стереть)\s+(?:задачу|пункт)?\s*(?:под номером)?\s*(\d+)', user_question_lower)
        delete_task_match_by_name = re.search(r'(удали|удалить|сотри|стереть)\s+(?:задачу|пункт)?\s+(.+)', user_question_lower)

        if delete_task_match_by_id:
            try:
                index = int(delete_task_match_by_id.group(2))
                return self.db_manager.delete_todo(index)
            except ValueError:
                return "Неверный номер задачи. Пожалуйста, укажите число."
        elif delete_task_match_by_name:
            task_name = delete_task_match_by_name.group(2).strip()
            return self.db_manager.delete_todo_by_name(task_name)
        
        if re.search(r'(покажи|показать|список|мои)\s+(?:задачи|память|что нужно сделать|туду)', user_question_lower):
            return self.db_manager.get_todos()


        weather_pattern = re.search(r'(?:какая|узнать|скажи|подскаж[ие]|расскажи|).+?погод[ау].*(?:в|сейчас|сегодня|завтра|на улице).*', user_question_lower)
        if weather_pattern:
            # Преобразуем в поисковый запрос
            search_result = search_web(f"текущая погода {user_question_lower}")
            prompt_for_llm = f"""На основе приведенных ниже результатов поиска в интернете, дай четкий и структурированный ответ о погоде.

        **Вопрос пользователя:** {user_question}

        **Результаты поиска:**
        ---
        {search_result}
        ---

        **Твой ответ:**"""
            return self.handle_chat_request(prompt_for_llm, chat_id)

        if user_question.startswith('!import ') and '\\n' in user_question:
            lines = user_question.split('\\n', 1)
            command_line = lines[0]
            filename = command_line[len('!import '):].strip()
        
            possible_paths = [
                os.path.join(config_setting.IMAGES_DIR, filename),
                filename  
            ]
        
            image_found = False
            for image_path in possible_paths:
                if os.path.isfile(image_path):
                    self.current_image_path = image_path
                    self.last_image_filename = filename
                    image_found = True
                    break
        
            if image_found:
                user_question = lines[1].strip() if len(lines) > 1 and lines[1].strip() else "Опиши это изображение."
            else:
                return f"Файл '{filename}' не найден. Проверьте имя файла и убедитесь, что он находится в папке images."
            
        web_search_match = re.search(r'^(найди|поищи|что|кто|расскажи|какая|какой|какие|сколько|когда|где|почему|зачем|узнай|информация|данные|опиши|объясни)\s+(?:в\s+интернете\s+)?(.+)', user_question_lower)
        if web_search_match:
            print(f"[DEBUG] Обнаружен запрос на веб-поиск: {user_question}")
            search_query = web_search_match.group(2)
            print(f"[DEBUG] Извлеченный поисковый запрос: {search_query}")
            query = web_search_match.group(2).strip()
    
            print(f"🤖 Выполняется веб-поиск по запросу: '{query}'")
    
            search_result = search_web(query)
    
            prompt_for_llm = f"""На основе приведенных ниже результатов поиска в интернете, дай четкий и структурированный ответ на вопрос пользователя.

        **Вопрос пользователя:** {query}

        **Результаты поиска:**
        ---
        {search_result}
        ---

        **Твой ответ:**"""
    
            agent_response = self.handle_chat_request(prompt_for_llm, chat_id)
            return agent_response
        return self.handle_chat_request(user_question, chat_id)
    def run(self):
        print("[DEBUG] Запуск метода run...")
        if not self.initialize_models():
            print("Не удалось инициализировать модели. Завершение работы.")
            if self.server_ready_event:
                self.server_ready_event.set()
            return

        HOST = config_setting.API_HOST
        PORT = config_setting.API_PORT

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((HOST, PORT))
            server_socket.listen(1)
            print(f"[Jane Assistant] Слушает на {HOST}:{PORT}")

            if self.server_ready_event:
                self.server_ready_event.set()

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
                    with conn:
                        data = conn.recv(8096)
                        if not data:
                            continue
                        try:
                            request = json.loads(data.decode())
                            user_message = request.get("message", "")
                            chat_id = request.get("chat_id", None) 
                            if not user_message:
                                response = {"error": "Пустое сообщение"}
                            else:
                                if not self.is_agent_active():
                                    print("Ошибка: Агент не активен")
                                    response = {"error": "Сервис временно недоступен"}
                                else:
                                    sanitized_message = sanitize_input(user_message)
                                    
                                    agent_response = self.ask(sanitized_message, chat_id) 
                                    
                                    response = {"response": agent_response}
                            conn.sendall(json.dumps(response).encode())
                        except Exception as e:
                            import traceback
                            print(traceback.format_exc())
                            if isinstance(e, queue.Empty) or "timed out" in str(e):
                                response = {"error": "timed out"}
                            else:
                                response = {"error": str(e)}
                                
                            conn.sendall(json.dumps(response).encode())
                except Exception as e:
                    print(f"Ошибка в основном цикле сервера: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    if not self.is_agent_active():
                        break

def API_model(agent, server_ready_event: Optional[threading.Event] = None): 
    try:
        jane = JaneAssistant(agent, server_ready_event) 
        jane.run()
    except Exception as e:
        print(f"Ошибка в API_model: {str(e)}")
        import traceback
        traceback.print_exc()
