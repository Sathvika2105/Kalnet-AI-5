@echo off
setlocal
set ROOT=%~dp0
echo ========================================
echo   Kalnet AI-5 Dashboard - Starting...
echo ========================================
echo.

:: Build React frontend first
echo [1/2] Building React frontend...
cd /d "%ROOT%frontend"
call npm run build
if %errorlevel% neq 0 (
    echo ERROR: Frontend build failed!
    pause
    exit /b 1
)
echo Frontend built successfully.
echo.

:: Start FastAPI Backend (serves both API and frontend)
echo [2/2] Starting server on http://localhost:8000
cd /d "%ROOT%"
start "Kalnet AI-5" cmd /k "uvicorn api.app:app --reload --host 0.0.0.0 --port 8000"

echo.
echo ========================================
echo   Dashboard ready at:
echo   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo ========================================
echo.
pause
