@echo off
rem =======================================================================
rem J.A.R.V.I.S. Windows Startup Installer
rem Adds or removes J.A.R.V.I.S. from Windows Startup
rem =======================================================================

if "%1"=="--uninstall" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_startup.ps1" -Uninstall
    goto end
)
if "%1"=="-u" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_startup.ps1" -Uninstall
    goto end
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_startup.ps1"

:end
pause
