# حفظ هذا النص في build_waraqat.bat داخل المجلد نفسه
@echo off
cd C:\Users\Administrator\Desktop\UniversalDownloader
pyinstaller --noconfirm --onefile --windowed ^
  --icon=assets\waraqat_icon.ico ^
  --name=Waraqat ^
  --add-data "assets;assets" ^
  --collect-all customtkinter ^
  --collect-all arabic_reshaper ^
  main.py
echo ---- BUILD DONE ----
pause