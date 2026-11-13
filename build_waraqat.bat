REM Build script for Waraqat
@echo off
setlocal
cd /d "%~dp0"

python -m PyInstaller --noconfirm --onefile --windowed ^
  --icon=assets\waraqat_icon.ico ^
  --name=Waraqat ^
  --add-data "assets;assets" ^
  --collect-all customtkinter ^
  --collect-all plyer ^
  main.py

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [ERROR] Build failed. Check the PyInstaller output above.
  pause
  exit /b 1
)

echo ---- BUILD DONE ----
pause
