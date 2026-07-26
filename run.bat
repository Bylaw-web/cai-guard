@echo off
REM CAI Guard — one-click launcher (installs deps first run, then starts the app in your tray)
python -m pip install -q -r "%~dp0requirements.txt"
python -m caiguard app
