@echo off
setlocal
cd /d "%~dp0webcam-game"
if not exist ".venv-existing\Scripts\python.exe" (
    echo First run start-webcam-game.bat once to install the game environment.
    pause
    exit /b 1
)
".venv-existing\Scripts\python.exe" main.py --camera 0 --difficulty hard
if errorlevel 1 pause
