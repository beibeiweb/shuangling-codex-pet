@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 scripts\bootstrap.py install
) else (
  python scripts\bootstrap.py install
)
if errorlevel 1 echo Installation failed. Python 3.11+ is required. Read README.md for details.
pause
