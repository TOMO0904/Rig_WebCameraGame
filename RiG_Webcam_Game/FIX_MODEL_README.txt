RiG++ Webcam Game - Windows Unicode path fix

This version avoids MediaPipe native code opening the .task model via its
Windows path. It reads the model in Python as bytes first.

1. Unzip the fixed archive to any folder (including Japanese OneDrive paths).
2. Open RiG_Webcam_Game.
3. Double-click start-webcam-game.bat.
4. The official Google hand model is downloaded if needed.

To keep your existing .venv-existing environment without reinstallation:
Copy just the modified webcam-game\main.py into your existing project's
webcam-game folder, replacing main.py. Then double-click your existing
start-webcam-game.bat.

If it still fails, screenshot all terminal lines.
No GitHub changes or uploads are performed by these launchers.
