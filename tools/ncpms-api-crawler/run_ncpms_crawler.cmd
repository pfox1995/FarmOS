@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo [NCPMS Crawler] NCPMS API 데이터를 수집하여 ncpms_data.json을 생성합니다...
cd ..\..\backend

where uv >nul 2>&1
if errorlevel 1 (
  echo [NCPMS Crawler] ERROR: uv가 설치되어 있지 않거나 PATH에 없습니다.
  pause
  exit /b 1
)

uv run python ..\tools\ncpms-api-crawler\ncpms-crawler.py
if errorlevel 1 (
  echo [NCPMS Crawler] 수집 중 에러가 발생했습니다.
  pause
  exit /b 1
)

echo [NCPMS Crawler] 수집 완료! JSON 파일이 업데이트되었습니다.
pause
