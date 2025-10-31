@echo off
REM ============================================
REM NutriAI Bot - Open Metrics Dashboard
REM ============================================

echo.
echo Opening NutriAI Bot Dashboard...
echo.
echo Dashboard will open in your default browser.
echo Make sure the bot is running (start.bat)
echo.

REM Open dashboard in default browser
start "" "%~dp0dashboard.html"

echo Dashboard opened!
echo.
echo To access metrics directly: http://localhost:8000/metrics
echo.
pause
