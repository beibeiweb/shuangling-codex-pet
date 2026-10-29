@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 scripts\bootstrap.py uninstall
) else (
  python scripts\bootstrap.py uninstall
)
pause
