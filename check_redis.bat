@echo off
echo ========================================
echo   Checking Redis Connection
echo ========================================
echo.

REM Activate virtual environment if exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo Testing Redis connection...
echo.

python -c "import redis; r = redis.from_url('redis://localhost:6379/0'); print('✓ Redis is running!' if r.ping() else '✗ Redis connection failed'); print(f'Redis info: {r.info(\"server\")[\"redis_version\"]}')" 2>nul

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ✗ Redis connection failed!
    echo.
    echo Please check:
    echo   1. Is Redis/Memurai installed and running?
    echo   2. Run: memurai-cli ping
    echo   3. Check port 6379 is not blocked
    echo.
    echo To install redis package: pip install redis
)

echo.
pause
