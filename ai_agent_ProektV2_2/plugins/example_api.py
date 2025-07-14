import time
import re

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

import re

def clean_response(text):
    text = re.sub(r'<think>.*?</think>\n*', '', text, flags=re.DOTALL)
    text = re.sub(r'</think>', '', text)
    text = re.sub(r'^Джейн:\s*', '', text)

    lines = text.strip().splitlines()
    cleaned_lines = []
    seen_lines = set()

    skip_keywords = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(kw in line.lower() for kw in skip_keywords):
            continue
        if line not in seen_lines:
            cleaned_lines.append(line)
            seen_lines.add(line)

    return '\n'.join(cleaned_lines)

def API_model(agent):
    iointel_models = {
        'api': 'iointelligence',
        'endpoint': 'models',
        'method': 'GET',
        'params': {},
        'request_id': f'req_iointel_models_{int(time.time()*1000)}'
    }
    agent.submit_request(iointel_models)

    max_retries = 5
    initial_delay = 2

    for attempt in range(max_retries):
        response_models = agent.get_response(iointel_models['request_id'], timeout=15)
        if response_models.get('status') == 'error' and '429' in response_models.get('error', ''):
            delay = min(initial_delay * (2 ** attempt), 30)
            time.sleep(delay)
            agent.submit_request(iointel_models)
        else:
            break
    else:
        return

    if response_models.get('status') == 'success' and 'data' in response_models:
        models_data = response_models['data'].get('data', [])
        model_ids = [model['id'] for model in models_data if 'id' in model]
        if not model_ids:
            return

        selected_index = 1
        model_name = model_ids[selected_index - 1]
    else:
        return

    print("Привет! Я Джейн — ваш ИИ-ассистент. Задайте вопрос или напишите «Пока, Джейн», чтобы завершить.")

    while True:
        user_question = input("Вы: ")
        if user_question.lower() in ['пока', 'пока джейн', 'до свидания', 'выход']:
            print("До встречи!")
            break

        if is_assistant_name_question(user_question):
            print("Меня зовут Джейн. Я ИИ-ассистент, готова помочь вам с различными вопросами.")
            continue

        request_id = f'req_iointel_chat_{int(time.time()*1000)}'
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
                            'Ты — ИИ-ассистент по имени Джейн. Ты всегда отвечаешь строго по запросу. '
                            'Никогда не объясняй, что ты делаешь, не добавляй комментариев, не рассуждай. '
                            'Если пользователь просит код — выводи только сам код, без описаний. '
                            'Если просит анекдот — строго один анекдот. Не повторяй, не вариируй. '
                            'Всегда пиши только один точный, прямой, развёрнутый ответ, без метаразмышлений.'
                        )
                    },
                    {'role': 'user', 'content': user_question}
                ]
            },
            'request_id': request_id
        }

        agent.submit_request(chat_request)

        for attempt in range(max_retries):
            chat_response = agent.get_response(request_id, timeout=30)
            if chat_response.get('status') == 'error' and '429' in chat_response.get('error', ''):
                delay = min(initial_delay * (2 ** attempt), 30)
                time.sleep(delay)
                agent.submit_request(chat_request)
            else:
                if chat_response.get('status') == 'success':
                    choices = chat_response['data'].get('choices', [])
                    if choices and 'message' in choices[0]:
                        text = choices[0]['message']['content']
                        cleaned_response = clean_response(text)
                        print("Джейн:", cleaned_response)
                    else:
                        print("Неверный ответ модели:", chat_response)
                else:
                    print("Ошибка ответа:", chat_response.get('error', 'Неизвестно'))
                break
        else:
            print("Слишком много попыток. Ответ не получен.")
