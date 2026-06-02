@echo off
title Dota Draft Helper

echo ============================================
echo  Dota Draft Helper
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM Check Node
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js not found. Please install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)

REM Install backend dependencies
echo Checking Python dependencies...
pip install -r backend\requirements.txt -q 2>nul

REM Always rebuild frontend so latest code changes are reflected
echo Building frontend...
cd frontend
call npm install -q --prefer-offline 2>nul
call npm run build
cd ..
if %errorlevel% neq 0 (
    echo ERROR: Frontend build failed.
    pause
    exit /b 1
)

echo.
echo Starting backend on http://localhost:4000 ...
echo Open the Draft Helper : http://localhost:4000
echo Open the Simulator    : http://localhost:4000/simulator
echo Press Ctrl+C to stop.
echo.

REM Open browser after 2 seconds
start /min cmd /c "timeout /t 2 >nul && start http://localhost:4000"

REM Start backend
cd backend
python main.py
