@echo off
REM ============================================================
REM  CAI Guard — build the installable Windows program.
REM  Run this from the repo root:   packaging\build.bat
REM  Produces:  dist\CAIGuard\CAIGuard.exe  (windowed, no console)
REM ============================================================
setlocal
cd /d "%~dp0.."

echo [1/3] Creating build environment...
python -m venv .buildenv 2>nul
call .buildenv\Scripts\activate.bat

echo [2/3] Installing dependencies + PyInstaller...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt pyinstaller

echo [3/3] Building CAIGuard.exe...
pyinstaller --noconfirm --clean packaging\CAIGuard.spec

echo.
echo Done. Portable app:  dist\CAIGuard\CAIGuard.exe
echo Next, build the installer with Inno Setup:  packaging\CAIGuard.iss
endlocal
