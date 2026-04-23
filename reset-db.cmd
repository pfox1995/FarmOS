@echo off
setlocal

echo =======================================================
echo FarmOS Database Wipe Utility
echo =======================================================

echo.
echo WARNING: This command will erase ALL data from the FarmOS database!
echo Are you absolutely sure you want to proceed?
echo.
pause

set PROJECT_ROOT=%~dp0
cd /d "%PROJECT_ROOT%backend"

:: Run the python reset script using uv
uv run python "%PROJECT_ROOT%bootstrap\reset_db.py"
if errorlevel 1 (
	echo.
	echo [ERROR] Database wipe failed or was aborted.
	cd /d "%PROJECT_ROOT%"
	pause
	exit /b 1
)

cd /d "%PROJECT_ROOT%"
echo.
echo If wiped successfully, run bootstrap.cmd to recreate and seed the database.
pause
