@echo off
REM One-click: build + install CAI Guard (no admin needed). Just double-click this file.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
