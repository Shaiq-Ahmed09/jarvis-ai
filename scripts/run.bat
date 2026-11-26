@echo off
cd /d "%~dp0\.."
where uv >nul 2>nul || (echo Install uv first: winget install astral-sh.uv   then run this file again & pause & exit /b)
if not exist .venv uv venv --python 3.12 .venv
call .venv\Scripts\activate
uv pip install -r requirements.txt
uvx playwright install chromium
if not exist .env (copy .env.example .env & echo Put your API key in .env, save, then run this file again. & notepad .env & exit /b)
start "" http://localhost:8765
python server.py
