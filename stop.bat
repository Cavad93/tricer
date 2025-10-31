@echo off
REM ============================================
REM NutriAI Bot - Stop Script for Windows
REM ============================================
REM This script stops all NutriAI Bot processes
REM ============================================

echo.
echo ============================================
echo  Stopping NutriAI Bot...
echo ============================================
echo.

REM Stop Celery processes
echo [1/2] Stopping Celery Worker...
taskkill /FI "WINDOWTITLE eq NutriAI Celery Worker*" /F >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Celery Worker stopped
) else (
    echo [INFO] No Celery Worker process found
)

REM Stop Bot processes
echo [2/2] Stopping NutriAI Bot...
taskkill /FI "WINDOWTITLE eq NutriAI Bot*" /F >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Bot stopped
) else (
    echo [INFO] No Bot process found
)

REM Also try to kill by process name as backup
tasklist | find "celery.exe" >nul
if %errorlevel% equ 0 (
    taskkill /IM celery.exe /F >nul 2>&1
    echo [OK] Stopped celery.exe processes
)

tasklist | find "python.exe" | find "app.bot.main" >nul
if %errorlevel% equ 0 (
    for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /NH') do (
        wmic process where "ProcessId=%%a" get CommandLine | find "app.bot.main" >nul
        if !errorlevel! equ 0 (
            taskkill /PID %%a /F >nul 2>&1
        )
    )
)

echo.
echo ============================================
echo  All NutriAI Bot processes stopped
echo ============================================
echo.
echo Note: Redis and PostgreSQL services are still running
echo To stop them manually:
echo   net stop Redis
echo   net stop postgresql-x64-15
echo.
pause
