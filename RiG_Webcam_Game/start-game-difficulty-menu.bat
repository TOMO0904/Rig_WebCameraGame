@echo off
setlocal
:menu
cls
echo ========================================
echo      RiG++ HAND DODGE+ PLAY MENU
echo ========================================
echo 1. EASY   - 5 lives, slow falling blocks
 echo 2. NORMAL - 3 lives, standard speed
 echo 3. HARD   - 2 lives, faster and more blocks
 echo.
choice /c 123 /n /m "Select 1-3: "
if errorlevel 3 (call "%~dp0start-webcam-hard.bat" & goto end)
if errorlevel 2 (call "%~dp0start-webcam-game.bat" & goto end)
if errorlevel 1 (call "%~dp0start-webcam-easy.bat" & goto end)
:end
endlocal
