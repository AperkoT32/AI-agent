import time
import re
import base64
import requests
import mimetypes
import os
import queue

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")
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

def extract_final_answer(text: str) -> str:
    # Пробуем найти <think></think>
    pattern_full = re.compile(r'<think>.*?</think>', re.DOTALL)
    match_full = pattern_full.search(text)
    if match_full:
        # Возвращаем текст после закрывающего тега </think>
        return text[match_full.end():].strip()

    # Если полного блока нет, ищем ТОЛЬКО ЗАКРЫВАЮЩИЙ тег </think> (НАКОНЕЦ ТО!!!)
    closing_tag = '</think>'
    if closing_tag in text:
        pos = text.find(closing_tag)
        return text[pos + len(closing_tag):].strip()

    # Если все и так окей:
    return text.strip()

def get_base64_uri(image_path: str) -> str:
    ext = os.path.splitext(image_path)[1][1:].lower()  # например 'jpg', 'png'
    if not ext:
        ext = 'jpeg'  # по дефолту

    mime_type = mimetypes.types_map.get(f'.{ext}', 'image/jpeg')

    with open(image_path, "rb") as f:
        b64_str = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{b64_str}"
def API_model(agent):
    global current_image_path
    max_retries = 5
    initial_delay = 2

    # Получаем список моделей
    iointel_models = {
        'api': 'iointelligence',
        'endpoint': 'models',
        'method': 'GET',
        'params': {},
        'request_id': f'req_iointel_models_{int(time.time()*1000)}'
    }

    model_name_for_text = None
    model_name_for_image = None

    # Запрашиваем модели с retry
    for attempt in range(max_retries):
        iointel_models['request_id'] = f'req_iointel_models_{int(time.time()*1000)}'
        agent.submit_request(iointel_models)
        try:
            response_models = agent.get_response(iointel_models['request_id'], timeout=60)
        except queue.Empty:
            print(f"Попытка {attempt + 1}: Время ожидания ответа модели истекло.")
            if attempt == max_retries -1:
                print("Не удалось получить список моделей.")
                return
            delay = min(initial_delay * (2 ** attempt), 30)
            time.sleep(delay)
            continue

        if response_models.get('status') == 'error' and '429' in response_models.get('error',''):
            delay = min(initial_delay * (2 ** attempt), 30)
            print(f"Попытка {attempt + 1}: Ошибка 429, повтор через {delay} сек")
            time.sleep(delay)
            continue

        if response_models.get('status') == 'success':
            models_data = response_models['data'].get('data', [])
            model_ids = [m['id'] for m in models_data if 'id' in m]
            if len(model_ids) < 2:
                print("Недостаточно моделей для выбора (ождалось 2)")
                return

            # Для примера:
            # model_name_for_text — первая модель для текстовых запросов
            # model_name_for_image — вторая модель для изображений, если нужно
            model_name_for_text = model_ids[0]
            model_name_for_image = model_ids[4]
            print(f"Модель для текста: {model_name_for_text}")
            print(f"Модель для изображений: {model_name_for_image}")
            break
        else:
            print(f"Ошибка получения списка моделей: {response_models.get('error', 'неизвестно')}")
            return

    print("Привет! Я Джейн — ваш ИИ-ассистент. Задайте вопрос или напишите «Пока», чтобы завершить.")
    print("Для работы с картинками напишите команду !import <название> + (.jpg/.png).")

    while True:
        user_question = input("Вы: ")
        if user_question.strip().lower() in ['пока', 'пока, джейн', 'до свидания', 'выход', 'exit']:
            print("До встречи!")
            break

        if is_assistant_name_question(user_question):
            print("Меня зовут Джейн. Я ИИ-ассистент, готова помочь вам с различными вопросами.")
            continue

        if not is_meaningful_question(user_question):
            print("Мне сложно понять ваш запрос. Можете, пожалуйста, уточнить или переформулировать? "
                  "Я с радостью помогу!")
            continue

        if user_question.startswith('!import '):
            filename = user_question[len('!import '):].strip()
            image_path = os.path.join(IMAGES_DIR, filename)
            if os.path.isfile(image_path):
                current_image_path = image_path
                print(f"Изображение '{filename}' загружено и будет использовано в следующем запросе.")
            else:
                print(f"Файл '{filename}' не найден в папке '{IMAGES_DIR}'. Проверьте имя и попробуйте снова.")
            continue

        # Выбираем модель в зависимости от того, есть ли изображение
        model_name = model_name_for_image if current_image_path else model_name_for_text

        base_chat_request = {
            'api': 'iointelligence',
            'endpoint': 'chat/completions',
            'method': 'POST',
            'params': {
                'model': model_name,
                'messages': [
                    {
                        'role': 'system',
                        'content': (
                            'Ты — ИИ-ассистент по имени Джейн. '
                            'Всегда отвечай строго по запросу, лаконично и по существу. '
                            'На общие вопросы, такие как "Как дела?", "Привет", "Чем занимаешься?", отвечай кратко, '
                            'дружелюбно, без лишних деталей и сразу переходи к делу или предлагай помощь.'
                            'Никогда не объясняй свои действия, не добавляй комментариев, не рассуждай, не используй '
                            'метаразмышления, если этого не требует пользователь. '
                            'Если пользователь просит код — выводи только сам код, без описаний, если их не требует '
                            'пользователь.'
                            'Не повторяй и не вариируй ответы в целом, если этого не требует пользователь. '
                            'Всегда пиши только один точный, прямой, развёрнутый ответ, без лишнего текста.'
                        )
                    },
                    {'role': 'user', 'content': user_question}
                ]
            }
        }

        max_retries_chat = 5
        initial_delay_chat = 2

        for attempt in range(max_retries_chat):
            request_id = f'req_iointel_chat_{int(time.time() * 1000)}'

            if current_image_path:
                base64_image_uri = get_base64_uri(current_image_path)
                # Формируем content как список с текстом и изображением
                user_content = [
                    {"type": "text", "text": user_question},
                    {"type": "image_url", "image_url": {"url": base64_image_uri}}
                ]
            else:
                user_content = user_question

            # Формируем словарь запроса заново с обновлённым content
            chat_request = {
                'api': 'iointelligence',
                'endpoint': 'chat/completions',
                'method': 'POST',
                'params': {
                    'model': model_name,
                    'messages': [
                        {
                            'role': 'system',
                            'content': (
                                'Ты — ИИ-ассистент по имени Джейн. '
                                'Всегда отвечай строго по запросу, лаконично и по существу. '
                                'На общие вопросы, такие как "Как дела?", "Привет", "Чем занимаешься?", '
                                'отвечай кратко, дружелюбно, без лишних деталей и сразу переходи к делу или предлагай '
                                'помощь.'
                                'Никогда не объясняй свои действия, не добавляй комментариев, не рассуждай, не используй '
                                'метаразмышления, если этого не требует пользователь. '
                                'Если пользователь просит код — выводи только сам код, без описаний, если их не требует '
                                'пользователь.'
                                'Не повторяй и не вариируй ответы в целом, если этого не требует пользователь. '
                                'Всегда пиши только один точный, прямой, развёрнутый ответ, без лишнего текста.'
                            )
                        },
                        {
                            'role': 'user',
                            'content': user_content
                        }
                    ]
                },
                'request_id': request_id
            }

            agent.submit_request(chat_request)

            if current_image_path:
                current_image_path = None

            try:
                chat_response = agent.get_response(request_id, timeout=30)
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
                else:
                    print("Неверный ответ модели:", chat_response)
                break
            else:
                print("Ошибка ответа:", chat_response.get('error', 'Неизвестно'))
                break
