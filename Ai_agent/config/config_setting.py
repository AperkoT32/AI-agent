
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = 8000

API_HOST = "127.0.0.1"
API_PORT = 5050

DATABASE_PATH = "data/jane_assistant.db"
IMAGES_DIR = "data/images"
GIFT_DIR = "data/gift"


# Приоритетный список моделей для текстовых задач
TEXT_MODEL_PREFERENCES = [
    'gpt-4', 
    'gpt-3.5-turbo', 
    'claude'
]

IMAGE_MODEL_PREFERENCES = [
    'Qwen/Qwen2.5-VL-32B-Instruct',
    'gpt-4-vision', 
    'claude-3-opus', 
    'claude-3-sonnet', 
    'gemini-pro-vision'
]

MAX_HISTORY_LENGTH = 10
MAX_RETRIES = 5
INITIAL_DELAY = 2

# Простая защита для демонстрации
DEMO_USERNAME = "Gamid"  # Измените на желаемое имя пользователя
DEMO_PASSWORD = "polekorov"  # Измените на желаемый пароль
