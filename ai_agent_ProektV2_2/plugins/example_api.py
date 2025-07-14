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
    pattern = re.compile(r'<think>.*?</think>', re.DOTALL)
    match = pattern.search(text)
    if match:
        return text[match.end():].strip()
    else:
        return text.strip()

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

        if not is_meaningful_question(user_question):
            print("Мне сложно понять ваш запрос. Можете, пожалуйста, уточнить или переформулировать? "
                  "Я с радостью помогу!")
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
                        # print("Raw model response:\n", text)  #- без обработки, логирование хода мысли

                        text_no_think = extract_final_answer(text)

                        cleaned_response = clean_response(text_no_think)
                        print(cleaned_response)
                    else:
                        print("Неверный ответ модели:", chat_response)
                else:
                    print("Ошибка ответа:", chat_response.get('error', 'Неизвестно'))
                break
        else:
            print("Слишком много попыток. Ответ не получен.")
