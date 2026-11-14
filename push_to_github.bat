@echo off
setlocal
cd /d "%~dp0"
set PATH=%~dp0tools\git\cmd;%~dp0tools\gh;%PATH%

title J.A.R.V.I.S. GitHub Sync Protocol
color 0b

echo ================================================================
echo      J.A.R.V.I.S. // GITHUB REPOSITORY DISPATCH PROTOCOL
echo ================================================================
echo.

gh auth status >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] GitHub authentication required.
    echo [*] Opening browser authorization window...
    echo [*] Your one-time verification code will be copied to clipboard!
    echo.
    gh auth login --web --clipboard -p https
)

echo.
echo [*] Checking authentication status...
gh auth status
if %errorlevel% neq 0 (
    echo [X] Authentication failed or was cancelled.
    pause
    exit /b 1
)

echo.
echo [*] Checking remote origin...
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Creating GitHub repository 'jarvis-ai' and pushing codebase...
    gh repo create jarvis-ai --public --source=. --remote=origin --push
    if %errorlevel% neq 0 (
        echo [!] Creating repository returned error code. Linking origin to user profile...
        for /f "tokens=*" %%u in ('gh api user -q .login') do (
            git remote add origin https://github.com/%%u/jarvis-ai.git 2>nul
            git remote set-url origin https://github.com/%%u/jarvis-ai.git
            git push -u origin main
        )
    )
) else (
    echo [*] Remote origin detected. Pushing latest commits to main...
    git push -u origin main
)

echo.
echo ================================================================
echo   [OK] Codebase successfully synchronized with GitHub!
echo ================================================================
pause
