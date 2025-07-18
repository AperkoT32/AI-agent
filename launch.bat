@echo off

IF NOT EXIST ".venv\Scripts\python.exe" (
	echo Creating .venv...
	python -m venv .venv
	echo Installing requirements...
	".venv\Scripts\pip.exe" install -r requirements.txt
)
echo Agent started! owo
".venv\Scripts\python.exe" main.py
pause