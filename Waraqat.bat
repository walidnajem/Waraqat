@echo off
chcp 65001 >nul
title Waraqat - ورقات
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: 1. Check if Python is installed on the machine
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ==============================================================
    echo [!] Python is not installed on this computer.
    echo [!] لغة بايثون غير مثبتة على هذا الحاسوب.
    echo [!] Please install Python from https://www.python.org/ and check 'Add to PATH'.
    echo ==============================================================
    pause
    exit /b 1
)

:: 2. Check if required libraries are installed
python -c "import requests, bs4, customtkinter, PIL, tqdm, plyer" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ==============================================================
    echo [*] Waraqat: First time setup - Installing required libraries...
    echo [*] ورقات: الإعداد للمرة الأولى - جاري تثبيت المكونات المطلوبة تلقائيا...
    echo [*] Please wait a moment / يرجى الانتظار بضع ثوان فقط...
    echo ==============================================================
    echo.
    python -m pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [ERROR] Failed to install libraries. Please check your internet connection.
        echo [خطأ] تعذر تحميل المكتبات، يرجى التأكد من اتصال الإنترنت.
        pause
        exit /b 1
    )
    echo.
    echo [*] Components installed successfully! Launching Waraqat...
    echo [*] تم تثبيت المكونات بنجاح! جاري تشغيل البرنامج...
    echo.
)

:: 3. Launch Waraqat
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ==============================================================
    echo [ERROR] An error occurred while running Waraqat.
    echo ==============================================================
    pause
)
