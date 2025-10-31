@echo off
REM ============================================
REM NutriAI Bot - Startup Script for Windows
REM ============================================
REM This script starts all necessary services for the bot:
REM 1. Redis (if not running)
REM 2. PostgreSQL (if not running)
REM 3. Celery Worker (background tasks)
REM 4. NutriAI Bot (main application)
REM ============================================

echo.
echo ============================================
echo  Starting NutriAI Bot...
echo ============================================
echo.

REM Check if we're in the correct directory
if not exist "app\bot\main.py" (
    echo ERROR: Please run this script from the tricer directory!
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM ============================================
REM Step 1: Check and start Redis
REM ============================================
echo [1/4] Checking Redis service...

sc query Redis >nul 2>&1
if %errorlevel% equ 0 (
    sc query Redis | find "RUNNING" >nul
    if %errorlevel% equ 0 (
        echo [OK] Redis is already running
    ) else (
        echo [STARTING] Starting Redis service...
        net start Redis >nul 2>&1
        if %errorlevel% equ 0 (
            echo [OK] Redis started successfully
        ) else (
            echo [WARNING] Could not start Redis service
            echo Please start Redis manually: redis-server --service-start
        )
    )
) else (
    echo [WARNING] Redis service not found
    echo Please install Redis and configure it as a Windows service
    echo Or start it manually: redis-server
)

timeout /t 2 /nobreak >nul

REM ============================================
REM Step 2: Check and start PostgreSQL
REM ============================================
echo.
echo [2/4] Checking PostgreSQL service...

sc query postgresql* >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=3" %%a in ('sc query postgresql* ^| findstr "STATE"') do set PG_STATE=%%a
    if "%PG_STATE%"=="RUNNING" (
        echo [OK] PostgreSQL is already running
    ) else (
        echo [STARTING] Starting PostgreSQL service...
        net start postgresql* >nul 2>&1
        if %errorlevel% equ 0 (
            echo [OK] PostgreSQL started successfully
        ) else (
            echo [WARNING] Could not start PostgreSQL service
            echo Please start PostgreSQL manually
        )
    )
) else (
    echo [WARNING] PostgreSQL service not found
    echo Please make sure PostgreSQL is installed
)

timeout /t 2 /nobreak >nul

REM ============================================
REM Step 3: Start Celery Worker in new window
REM ============================================
echo.
echo [3/4] Starting Celery Worker...

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.11+ and add it to PATH
    pause
    exit /b 1
)

REM Start Celery in a new window
start "NutriAI Celery Worker" cmd /k "cd /d %CD% && echo Starting Celery Worker... && celery -A app.celery_app worker --loglevel=info --pool=solo --concurrency=1"

echo [OK] Celery Worker started in new window
timeout /t 3 /nobreak >nul

REM ============================================
REM Step 4: Start Bot in new window
REM ============================================
echo.
echo [4/4] Starting NutriAI Bot...

REM Start Bot in a new window
start "NutriAI Bot" cmd /k "cd /d %CD% && echo Starting NutriAI Bot... && python -m app.bot.main"

echo [OK] Bot started in new window
timeout /t 2 /nobreak >nul

REM ============================================
REM Done!
REM ============================================
echo.
echo ============================================
echo  NutriAI Bot started successfully!
echo ============================================
echo.
echo Two new windows have been opened:
echo   1. Celery Worker (background tasks)
echo   2. NutriAI Bot (main application)
echo.
echo To stop the bot:
echo   - Close both windows, or press Ctrl+C in each
echo.
echo Monitoring:
echo   - Bot metrics: http://localhost:8000/metrics
echo   - Grafana (if running): http://localhost:3000
echo.
echo Press any key to close this window...
pause >nul
