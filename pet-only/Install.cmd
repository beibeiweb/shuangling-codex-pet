@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-pet.ps1" -Action Install
set "result=%errorlevel%"
if not "%result%"=="0" echo Installation failed. Read the error above; previous pet files were preserved.
pause
exit /b %result%
