@echo off

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo Creating .venv...
    python -m venv .venv
    echo Upgrading pip...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    echo Installing requirements...
    ".venv\Scripts\pip.exe" install -r requirements.txt
) ELSE (
    echo Upgrading pip...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    echo Checking and updating packages...
    ".venv\Scripts\pip.exe" install -r requirements.txt --upgrade
)

echo Устанавливаю модель spaCy ru_core_news_lg (если уже есть — будет пропущено)...
".venv\Scripts\python.exe" -m spacy download ru_core_news_lg

echo Agent started! owo
".venv\Scripts\python.exe" main.py
echo.
echo Нажмите любую клавишу для выхода...
pause >nul