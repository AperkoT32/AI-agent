import uvicorn
from core.agent import AIAgent
from plugins.example_api import API_model
import threading

def main():
    # Инициализация и запуск ИИ-агента
    agent = AIAgent()
    agent.start()
    
    try:
        # Запуск API модели в отдельном потоке
        api_thread = threading.Thread(target=API_model, args=(agent,))
        api_thread.daemon = True
        api_thread.start()
        
        # Запуск веб-сервера
        uvicorn.run("web_server:app", host="127.0.0.1", port=8000, reload=False)
    finally:
        agent.stop()

if __name__ == "__main__":
    main()