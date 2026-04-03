@echo off
chcp 65001 >nul

echo ========================================
echo   FarmOS 전체 서비스 시작
echo ========================================
echo.
echo   FarmOS Backend   : http://localhost:8000
echo   FarmOS Frontend  : http://localhost:5173
echo   Shop Backend     : http://localhost:4000
echo   Shop Frontend    : http://localhost:5174
echo   Backoffice       : http://localhost:5174/admin
echo.

@REM 현재 스크립트가 위치한 경로를 작업 디렉토리로 설정
cd "%~dp0"

@REM FarmOS 백엔드
pushd "backend"
start "farmos_backend" uv run main.py
popd
@REM 쇼핑몰 백엔드
pushd "shopping_mall\backend"
start "shoppingmall_backend" uv run main.py
popd
@REM FarmOS 프론트엔드
pushd "frontend"
start "farmos_frontend" cmd /K "npm install && npm run dev"
popd
@REM 쇼핑몰 프론트엔드
pushd "shopping_mall\frontend"
start "shoppingmall_frontend" cmd /K "npm install && npm run dev"
popd

echo 모든 서비스가 시작되었습니다. 3초 후 현재 창이 닫힙니다.
timeout /T 3 /NOBREAK >nul

