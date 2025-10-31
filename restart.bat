@echo off
REM ============================================
REM NutriAI Bot - Restart Script for Windows
REM ============================================

echo.
echo ============================================
echo  Restarting NutriAI Bot...
echo ============================================
echo.

echo Step 1: Stopping all processes...
call stop.bat

echo.
echo Step 2: Waiting 5 seconds...
timeout /t 5 /nobreak

echo.
echo Step 3: Starting all processes...
call start.bat
