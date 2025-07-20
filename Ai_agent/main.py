import uvicorn
from core.agent import AIAgent
from plugins.example_api import API_model
import threading
import signal
import sys
import time
import config.config_setting as config_setting

def signal_handler(sig, frame):
    print('\nПолучен сигнал завершения. Останавливаем сервисы...')
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🚀 Запуск Jane AI Assistant...")
    
    agent = AIAgent()
    
    server_ready_event = threading.Event()
    
    try:
        agent.start()
        print("✅ AI Agent запущен")
        api_thread = threading.Thread(target=API_model, args=(agent, server_ready_event))
        api_thread.daemon = True
        api_thread.start()
        print("✅ API модель запущена")
        print("⏳ Ожидание запуска сервера AI-агента...")
        server_ready_event.wait(timeout=60) 
        if not server_ready_event.is_set():
            print("❌ Сервер AI-агента не запустился вовремя. Проверьте логи.")
            sys.exit(1)
        print("✅ Сервер AI-агента готов.")
        print(f"🌐 Запуск веб-сервера на http://{config_setting.WEB_SERVER_HOST}:{config_setting.WEB_SERVER_PORT}")
        print("📱 Откройте браузер и перейдите по адресу выше")
        print("⏹️  Для остановки нажмите Ctrl+C")
        
        uvicorn.run(
            "web_server:app", 
            host="0.0.0.0",  # Принудительно слушаем на всех интерфейсах
            port=config_setting.WEB_SERVER_PORT,
            reload=False,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        print("\n⏹️  Получен сигнал остановки...")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🔄 Останавливаем AI Agent...")
        agent.stop()
        print("✅ Jane AI Assistant остановлен")

if __name__ == "__main__":
    main()
