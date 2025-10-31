@echo off
REM ============================================
REM NutriAI Bot - Debug Startup Script
REM ============================================
REM This script starts the bot with DEBUG logging
REM to help diagnose connection issues
REM ============================================

echo.
echo ============================================
echo  Starting NutriAI Bot in DEBUG mode...
echo ============================================
echo.

REM Check if we're in the correct directory
if not exist "app\bot\main.py" (
    echo ERROR: Please run this script from the tricer directory!
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM Set DEBUG log level
set LOG_LEVEL=DEBUG

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    pause
    exit /b 1
)

echo [1/3] Checking .env file...
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Please create .env file with your bot token
    pause
    exit /b 1
)

REM Display token info (first 10 chars only for security)
for /f "tokens=1,2 delims==" %%a in (.env) do (
    if "%%a"=="TELEGRAM_BOT_TOKEN" (
        set BOT_TOKEN=%%b
        set BOT_TOKEN=!BOT_TOKEN: =!
        set BOT_TOKEN=!BOT_TOKEN:"=!
        echo [OK] Token found: !BOT_TOKEN:~0,10!...
    )
)
echo.

echo [2/3] Checking Redis...
redis-cli ping >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Redis is running
) else (
    echo [WARNING] Redis is not responding
    echo Trying to start Redis service...
    net start Redis >nul 2>&1
)
echo.

echo [3/3] Checking PostgreSQL...
sc query postgresql* | find "RUNNING" >nul
if %errorlevel% equ 0 (
    echo [OK] PostgreSQL is running
) else (
    echo [WARNING] PostgreSQL might not be running
)
echo.

echo ============================================
echo  Starting bot with DEBUG logging...
echo ============================================
echo.
echo IMPORTANT: Watch for these lines in the output:
echo   - "Prometheus metrics server started"
echo   - "Starting in POLLING mode"
echo   - "Bot started successfully"
echo   - Look for any ERROR or WARNING messages
echo.
echo Press Ctrl+C to stop the bot
echo.
pause

REM Start bot with DEBUG logging
python -m app.bot.main

echo.
echo Bot stopped.
pause
