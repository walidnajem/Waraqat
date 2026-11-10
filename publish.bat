@echo off
title Waraqat - Quick Publisher
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

python publish.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Publishing script encountered an issue.
    pause
    exit /b 1
)

pause
