@echo off
echo ========================================
echo   Starting NutriAI Telegram Bot
echo ========================================
echo.

REM Activate virtual environment if exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo Starting bot...
echo.

python main.py

pause
