import openai

openai.api_key = "Код API OPENAI" # Заменить на свой ключ API OPENAI для проверки работы ключа

def test_openai_api():
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Раз два проверка."}]
        )
        print(" Ключ работает. Ответ OpenAI:")
        print(response.choices[0].message.content)
    except openai.RateLimitError:
        print(" Ошибка:  (Rate Limit). Попробуй позже.")
    except openai.AuthenticationError:
        print(" Ошибка: неверный API ключ .")
    except openai.OpenAIError as e:
        print(f"  ошибка OpenAI: {e}")
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")

if __name__ == "__main__":
    test_openai_api()
