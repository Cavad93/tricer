@echo off
echo ========================================
echo   Starting Celery Worker for NutriAI
echo ========================================
echo.

REM Activate virtual environment if exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo Starting Celery worker with solo pool (Windows compatible)...
echo.
echo Keep this window open while the bot is running!
echo.

celery -A app.celery_app worker --loglevel=info --pool=solo

pause
