@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo [Bootstrap ] ERROR: python not found in PATH.
  echo [Bootstrap ] Install Python and try again.
  pause
  exit /b 1
)

python "%~dp0bootstrap.py" %*
pause
exit /b %errorlevel%
