@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo    AI Agent Launcher
echo ========================================
echo.

echo Проверяю наличие Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python не найден! Начинаю автоматическую установку...
    goto :install_python
) else (
    echo Python найден!
    python --version
    goto :check_venv
)

:install_python
echo.
echo Скачиваю Python 3.11...
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'python_installer.exe'}"

if not exist "python_installer.exe" (
    echo ОШИБКА: Не удалось скачать Python!
    echo Пожалуйста, установите Python вручную с https://python.org
    goto :error_exit
)

echo.
echo ========================================
echo Устанавливаю Python автоматически...
echo Python будет установлен с настройками:
echo - Добавление в PATH
echo - Установка для всех пользователей  
echo - Включение pip
echo.
echo ВНИМАНИЕ: Сейчас появится окно UAC
echo Нажмите "Да" для продолжения установки
echo Не закрывайте это окно!
echo ========================================
echo.

echo Установка начнется через 5 секунд...
for /l %%i in (5,-1,1) do (
    echo %%i...
    timeout /t 1 /nobreak >nul
)

echo Запускаю установку с правами администратора...
powershell -Command "Start-Process 'python_installer.exe' -ArgumentList '/quiet','InstallAllUsers=1','PrependPath=1','Include_test=0','Include_pip=1','Include_tcltk=1' -Verb RunAs -Wait"

echo Установка завершена!

echo Удаляю установщик...
del python_installer.exe

echo Обновляю переменные окружения...
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SystemPath=%%B"
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "UserPath=%%B"
set "PATH=%SystemPath%;%UserPath%"

echo Проверяю установку Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo ВНИМАНИЕ: Требуется перезапуск!
    echo ========================================
    echo Python установлен, но требуется перезапуск
    echo командной строки для обновления PATH.
    echo.
    echo Пожалуйста:
    echo 1. Закройте это окно
    echo 2. Откройте новую командную строку
    echo 3. Запустите launch.bat снова
    echo.
    echo Или перезагрузите компьютер и запустите снова.
    echo ========================================
    goto :error_exit
)

echo Python успешно установлен и настроен!
python --version

:check_venv
echo.
echo Проверяю виртуальное окружение...

if exist ".venv" (
    if not exist ".venv\Scripts\python.exe" (
        echo Удаляю поврежденное виртуальное окружение...
        rmdir /s /q ".venv"
    ) else (
        ".venv\Scripts\python.exe" --version >nul 2>&1
        if %errorlevel% neq 0 (
            echo Удаляю поврежденное виртуальное окружение...
            rmdir /s /q ".venv"
        )
    )
)

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo Создаю новое виртуальное окружение...
    python -m venv .venv --clear
    if %errorlevel% neq 0 (
        echo ОШИБКА: Не удалось создать виртуальное окружение!
        echo Попробуйте запустить от имени администратора
        goto :error_exit
    )
    
    echo Обновляю pip...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if %errorlevel% neq 0 (
        echo ОШИБКА: Не удалось обновить pip!
        goto :error_exit
    )
    
    echo Устанавливаю зависимости...
    ".venv\Scripts\pip.exe" install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ОШИБКА: Не удалось установить зависимости!
        echo Проверьте файл requirements.txt
        goto :error_exit
    )
) ELSE (
    echo Виртуальное окружение найдено!
    echo Проверяю работоспособность...
    ".venv\Scripts\python.exe" --version
    if %errorlevel% neq 0 (
        echo Виртуальное окружение повреждено, пересоздаю...
        rmdir /s /q ".venv"
        goto :check_venv
    )
    
    echo Обновляю pip...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    
    echo Проверяю и обновляю пакеты...
    ".venv\Scripts\pip.exe" install -r requirements.txt --upgrade
)

echo.
echo Проверяю модель spaCy ru_core_news_lg...

".venv\Scripts\python.exe" -c "import spacy; spacy.load('ru_core_news_lg')" >nul 2>&1
if %errorlevel% equ 0 (
    echo Модель spaCy ru_core_news_lg уже установлена!
    goto :start_app
)

echo Устанавливаю модель spaCy ru_core_news_lg...
echo Попытка 1: Стандартная установка...
".venv\Scripts\python.exe" -m spacy download ru_core_news_lg
if %errorlevel% equ 0 (
    echo Модель spaCy успешно установлена!
    goto :start_app
)

echo.
echo Попытка 2: Установка через pip с альтернативным источником...
".venv\Scripts\pip.exe" install https://github.com/explosion/spacy-models/releases/download/ru_core_news_lg-3.7.0/ru_core_news_lg-3.7.0-py3-none-any.whl
if %errorlevel% equ 0 (
    echo Модель spaCy успешно установлена через альтернативный источник!
    goto :start_app
)

echo.
echo Попытка 3: Установка через pip с основного индекса...
".venv\Scripts\pip.exe" install ru_core_news_lg
if %errorlevel% equ 0 (
    echo Модель spaCy успешно установлена через pip!
    goto :start_app
)

echo.
echo ========================================
echo ВНИМАНИЕ: Модель spaCy не установлена
echo ========================================
echo.
echo Не удалось автоматически установить модель spaCy.
echo Возможные причины:
echo - Проблемы с интернет-соединением
echo - Блокировка файрволом или антивирусом
echo - Проблемы с сертификатами SSL
echo.
echo Приложение будет запущено, но с ограниченной функциональностью.
echo.
echo Для ручной установки модели позже выполните:
echo ".venv\Scripts\python.exe" -m spacy download ru_core_news_lg
echo.
echo Нажмите любую клавишу для продолжения...
pause >nul

:start_app
echo.
echo ========================================
echo    Запускаю AI Agent! 🚀
echo ========================================
echo.

".venv\Scripts\python.exe" main.py

goto :normal_exit

:error_exit
echo.
echo ========================================
echo    ОШИБКА ЗАПУСКА!
echo ========================================
echo.
echo Нажмите любую клавишу для выхода...
pause >nul
exit /b 1

:normal_exit
echo.
echo ========================================
echo    AI Agent завершил работу
echo ========================================
echo.
echo Нажмите любую клавишу для выхода...
pause >nul
