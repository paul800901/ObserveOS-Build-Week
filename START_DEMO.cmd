@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or newer is required.
  exit /b 1
)
python app.py --open-browser
