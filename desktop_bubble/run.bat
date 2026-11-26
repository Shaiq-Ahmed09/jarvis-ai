@echo off
title J.A.R.V.I.S. Desktop AI Bubble (PySide6)
cd /d "%~dp0"
echo Launching J.A.R.V.I.S. Desktop AI Bubble...
if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" main.py %*
) else (
    python main.py %*
)
pause
