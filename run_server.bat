@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo Admission Management System - Local development
echo Sao luu database truoc lan chay dau ban moi.
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto fail
)
set "VENV_PY=.venv\Scripts\python.exe"
"%VENV_PY%" -m scripts.check_dependencies
if errorlevel 1 (
  "%VENV_PY%" -m pip install -r requirements.lock
  if errorlevel 1 goto fail
)
choice /c 12 /n /m "Chon 1=Local, 2=LAN: "
set "MODE=%errorlevel%"
set "APP_PORT=8000"
set /p "APP_PORT=Nhap port [8000]: "
if "%MODE%"=="2" (
  set /p "LAN_IP=Nhap IPv4 cua may: "
  goto lan
)
"%VENV_PY%" -m scripts.run_local --port "%APP_PORT%"
if errorlevel 1 goto fail
goto end
:lan
"%VENV_PY%" -m scripts.run_local --host 0.0.0.0 --lan-ip "%LAN_IP%" --port "%APP_PORT%"
if errorlevel 1 goto fail
goto end
:fail
echo Khoi dong that bai. Xem loi ben tren va README_DEPLOY.md.
pause
:end
endlocal
