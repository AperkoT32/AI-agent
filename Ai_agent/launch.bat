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
echo Checking spaCy language model...
".venv\Scripts\python.exe" -c "import spacy; exit(0) if 'ru_core_news_lg' in spacy.util.get_installed_models() else exit(1)" 2>nul
IF %ERRORLEVEL% NEQ 0 (
    echo SpaCy model ru_core_news_lg not found. Downloading...
    ".venv\Scripts\python.exe" -m spacy download ru_core_news_lg
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to download SpaCy model!
        pause
        exit /b 1
    )
    echo SpaCy model successfully downloaded.
) ELSE (
    echo SpaCy model ru_core_news_lg is already installed.
)

echo Installing PyTorch...
".venv\Scripts\pip.exe" install torch

echo Agent started! owo
".venv\Scripts\python.exe" main.py
pause