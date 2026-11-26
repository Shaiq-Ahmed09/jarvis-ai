@echo off
cd /d "%~dp0.."
call .venv\Scripts\activate
start python desktop_bubble\main.py --url http://localhost:8765
