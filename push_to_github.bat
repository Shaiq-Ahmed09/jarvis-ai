@echo off
setlocal
cd /d "%~dp0"
set PATH=%~dp0tools\git\cmd;%~dp0tools\gh;%PATH%

echo ===================================================
echo   J.A.R.V.I.S. GITHUB REPOSITORY DISPATCH PROTOCOL
echo ===================================================
echo.

gh auth status >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] GitHub authentication required. Launching one-click browser authorization...
    echo.
    gh auth login -w -p https
)

echo.
echo [*] Checking remote origin...
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Creating GitHub repository 'jarvis-ai' and pushing codebase...
    gh repo create jarvis-ai --public --source=. --remote=origin --push
) else (
    echo [*] Pushing latest commits to GitHub...
    git push -u origin main
)

echo.
echo [OK] Codebase successfully synchronized with GitHub!
pause
