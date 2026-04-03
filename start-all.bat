@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title FarmOS - All Services
cd /d "%~dp0"

echo.
echo  ============================================
echo    FarmOS - All Services Controller
echo  ============================================
echo.
echo    FarmOS Backend   : http://localhost:8000
echo    FarmOS Frontend  : http://localhost:5173
echo    Shop Backend     : http://localhost:4000
echo    Shop Frontend    : http://localhost:5174
echo.
echo  ============================================
echo.

REM Create logs directory
if not exist "logs" mkdir "logs"

REM Preflight checks
echo  [Preflight] Checking required tools...
where npm >nul 2>&1
if errorlevel 1 (
    echo  ERROR: npm not found. Please install Node.js and reopen terminal.
    goto :fail
)

where uv >nul 2>&1
if errorlevel 1 (
    echo  ERROR: uv not found. Install uv first: https://docs.astral.sh/uv/
    goto :fail
)

echo  [Preflight] Preparing backend dependencies...
call :ensure_uv_project "%~dp0backend" "FarmOS Backend" "%~dp0logs\farmos-be-setup.log"
if errorlevel 1 goto :fail

call :ensure_uv_project "%~dp0shopping_mall\backend" "Shop Backend" "%~dp0logs\shop-be-setup.log"
if errorlevel 1 goto :fail

echo  [Preflight] Preparing frontend dependencies...
call :ensure_npm_project "%~dp0frontend" "FarmOS Frontend" "%~dp0logs\farmos-fe-install.log"
if errorlevel 1 goto :fail

call :ensure_npm_project "%~dp0shopping_mall\frontend" "Shop Frontend" "%~dp0logs\shop-fe-install.log"
if errorlevel 1 goto :fail

echo  [Preflight] Done.
echo.

REM Start services
echo  [1/4] Starting FarmOS Backend...
start "FarmOS Backend" /B cmd /c "cd /d ""%~dp0backend"" && uv run main.py > ""%~dp0logs\farmos-be.log"" 2>&1"

echo  [2/4] Starting Shop Backend...
start "Shop Backend" /B cmd /c "cd /d ""%~dp0shopping_mall\backend"" && uv run main.py > ""%~dp0logs\shop-be.log"" 2>&1"

REM Allow backend startup time
timeout /T 3 /NOBREAK >nul

echo  [3/4] Starting FarmOS Frontend...
start "FarmOS Frontend" /B cmd /c "cd /d ""%~dp0frontend"" && npm run dev > ""%~dp0logs\farmos-fe.log"" 2>&1"

echo  [4/4] Starting Shop Frontend...
start "Shop Frontend" /B cmd /c "cd /d ""%~dp0shopping_mall\frontend"" && npm run dev > ""%~dp0logs\shop-fe.log"" 2>&1"

echo.
echo  All services started.
echo  Logs: logs\farmos-be.log, shop-be.log, farmos-fe.log, shop-fe.log
echo.
echo  ============================================
echo    Press any key to stop all services
echo  ============================================
echo.

REM Wait for user input to stop
pause >nul

echo.
echo  Stopping all services...

REM Kill process tree by listening ports
for %%P in (8000 4000 5173 5174) do (
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%%P " ^| findstr "LISTENING"') do (
        echo  Killing PID %%a (port %%P)...
        taskkill /PID %%a /T /F >nul 2>&1
    )
)

REM Cleanup any leftover node processes
taskkill /F /IM "node.exe" >nul 2>&1

echo.
echo  All services stopped.
echo.
pause
goto :eof

:ensure_npm_project
REM %1=projectPath %2=label %3=logFile
set "PROJECT_PATH=%~1"
set "PROJECT_LABEL=%~2"
set "PROJECT_LOG=%~3"

if not exist "%PROJECT_PATH%\package.json" (
    echo  ERROR: package.json not found for %PROJECT_LABEL% at %PROJECT_PATH%
    exit /b 1
)

if exist "%PROJECT_PATH%\node_modules" (
    echo   - %PROJECT_LABEL%: npm install already satisfied.
    exit /b 0
)

echo   - %PROJECT_LABEL%: node_modules missing. Running npm install...
pushd "%PROJECT_PATH%" >nul
call npm install > "%PROJECT_LOG%" 2>&1
set "NPM_EXIT=%ERRORLEVEL%"
popd >nul

if not "%NPM_EXIT%"=="0" (
    echo  ERROR: npm install failed for %PROJECT_LABEL%. See log: %PROJECT_LOG%
    exit /b 1
)

echo   - %PROJECT_LABEL%: npm install completed.
exit /b 0

:ensure_uv_project
REM %1=projectPath %2=label %3=logFile
set "PROJECT_PATH=%~1"
set "PROJECT_LABEL=%~2"
set "PROJECT_LOG=%~3"

if not exist "%PROJECT_PATH%\pyproject.toml" (
    echo  ERROR: pyproject.toml not found for %PROJECT_LABEL% at %PROJECT_PATH%
    exit /b 1
)

echo   - %PROJECT_LABEL%: running uv sync...
pushd "%PROJECT_PATH%" >nul
call uv sync > "%PROJECT_LOG%" 2>&1
set "UV_EXIT=%ERRORLEVEL%"
popd >nul

if not "%UV_EXIT%"=="0" (
    echo  ERROR: uv sync failed for %PROJECT_LABEL%. See log: %PROJECT_LOG%
    exit /b 1
)

echo   - %PROJECT_LABEL%: uv sync completed.
exit /b 0

:fail
echo.
echo  Startup aborted due to preflight errors.
echo  Check setup logs under logs\*.log
echo.
pause
exit /b 1
