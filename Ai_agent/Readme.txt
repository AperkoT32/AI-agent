Для быстрого запуска нужно воспользоваться батником под названием launch и смотреть пункт 5) и 6) . Если хотите идти по сложному, то сначала 

1. В  терминале пишите IDL  python -m venv .venv (===Создание виртуального окружения===)
2. В  терминале пишем venv\Scripts\activate ( ===Активация виртуального окружения===)
3. Устанавливаем зависимости pip install -r requirements.txt
4  Устанавливаем русификатор для модели  python -m spacy download ru_core_news_lg

5. Если всё нормально в терминале видим  

[Jane Assistant] Слушает на 127.0.0.1:5050
✅ Сервер AI-агента готов.
🌐 Запуск веб-сервера на http://127.0.0.1:8000
📱 Откройте браузер и перейдите по адресу выше
⏹️  Для остановки нажмите Ctrl+C
INFO:     Started server process [43972]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

6) Кликаем на  адрес или пишем в веб браузере http://127.0.0.1:8000
