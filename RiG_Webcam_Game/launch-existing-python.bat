@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "MODE=%~1"
set "CAMERA_ID=%~2"
cd /d "%~dp0webcam-game"
if errorlevel 1 goto failed

echo.
echo ============================================
echo RiG++ Webcam Game - Existing Python launcher
echo ============================================
echo.

rem Find an already-installed 64-bit Python between 3.9 and 3.14.
rem No new Python installation is performed.
set "PY_CMD="
python -c "import sys,struct; exit(0 if (3,9) <= sys.version_info[:2] <= (3,14) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
if not errorlevel 1 set "PY_CMD=python"
if not defined PY_CMD (
    py -3 -c "import sys,struct; exit(0 if (3,9) <= sys.version_info[:2] <= (3,14) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3"
)
if not defined PY_CMD (
    python3 -c "import sys,struct; exit(0 if (3,9) <= sys.version_info[:2] <= (3,14) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python3"
)
if not defined PY_CMD goto no_python

echo Found existing Python:
%PY_CMD% -c "import sys; print(sys.executable); print(sys.version.split()[0])"
if errorlevel 1 goto failed

rem Separate, isolated virtual environment; original Python is untouched.
set "ENV_DIR=.venv-existing"
set "ENV_PY=%ENV_DIR%\Scripts\python.exe"
if not exist "%ENV_PY%" (
    echo.
    echo [1/3] Creating an environment using installed Python...
    %PY_CMD% -m venv "%ENV_DIR%"
    if errorlevel 1 goto failed
)
"%ENV_PY%" -m pip --version >nul 2>&1
if errorlevel 1 (
    "%ENV_PY%" -m ensurepip --upgrade
    if errorlevel 1 goto failed
)

if /i "%MODE%"=="check" goto check
if /i "%MODE%"=="demo" goto demo
if /i "%MODE%"=="game" goto game

echo Unknown launcher mode: %MODE%
goto failed

:check
echo.
echo [2/3] Installing camera preview package...
"%ENV_PY%" -m pip install --only-binary=:all: "opencv-contrib-python>=4.8,<6" "numpy>=1.26,<3"
if errorlevel 1 goto failed
if not defined CAMERA_ID (
    set /p CAMERA_ID=Camera number [0]: 
)
if not defined CAMERA_ID set "CAMERA_ID=0"
echo [3/3] Starting webcam preview. Press Q or Esc to close.
"%ENV_PY%" check_camera.py --camera %CAMERA_ID%
if errorlevel 1 goto failed
goto finished

:demo
echo.
echo [2/3] Installing game display packages...
"%ENV_PY%" -m pip install --only-binary=:all: "opencv-contrib-python>=4.8,<6" "numpy>=1.26,<3"
if errorlevel 1 goto failed
echo [3/3] Starting demo without camera...
"%ENV_PY%" main.py --demo
if errorlevel 1 goto failed
goto finished

:game
echo.
echo [2/4] Installing hand tracking and video packages...
"%ENV_PY%" -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 goto failed
echo [3/4] Checking official hand detection model...
"%ENV_PY%" download_model.py
if errorlevel 1 goto failed
if not defined CAMERA_ID set "CAMERA_ID=0"
echo [4/4] Starting game with webcam %CAMERA_ID%...
"%ENV_PY%" main.py --camera %CAMERA_ID%
if errorlevel 1 goto failed
goto finished

:no_python
echo.
echo ERROR: No compatible installed Python was detected.
echo Required: 64-bit Python 3.9 through 3.14.
echo Install is NOT automatic. To check, run: py --list-paths
echo Or run: python --version
goto end

:failed
echo.
echo ERROR: Startup failed. Please screenshot or copy ALL lines above.
echo A download or compatibility error may need further diagnosis.
goto end

:finished
echo.
echo Application closed normally.

:end
echo.
pause
