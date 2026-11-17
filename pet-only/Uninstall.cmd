@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-pet.ps1" -Action Uninstall
set "result=%errorlevel%"
pause
exit /b %result%
