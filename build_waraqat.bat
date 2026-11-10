REM Build script for Waraqat
@echo off
cd C:\Users\Administrator\Desktop\UniversalDownloader
pyinstaller --noconfirm --onefile --windowed ^
  --icon=assets\waraqat_icon.ico ^
  --name=Waraqat ^
  --add-data "assets;assets" ^
  --collect-all customtkinter ^
  --collect-all arabic_reshaper ^
  --collect-all plyer ^
  main.py
echo ---- BUILD DONE ----
pause