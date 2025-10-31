@echo off
REM ============================================
REM Test Telegram API Connection
REM ============================================
echo.
echo ============================================
echo  Testing Telegram Bot API Connection
echo ============================================
echo.

REM Read bot token from .env
for /f "tokens=1,2 delims==" %%a in (.env) do (
    if "%%a"=="TELEGRAM_BOT_TOKEN" set BOT_TOKEN=%%b
)

if "%BOT_TOKEN%"=="" (
    echo [ERROR] TELEGRAM_BOT_TOKEN not found in .env file
    echo.
    pause
    exit /b 1
)

REM Remove any quotes or spaces from token
set BOT_TOKEN=%BOT_TOKEN:"=%
set BOT_TOKEN=%BOT_TOKEN: =%

echo [INFO] Testing with token: %BOT_TOKEN:~0,10%...
echo.

echo [1/3] Testing getMe endpoint...
curl -s https://api.telegram.org/bot%BOT_TOKEN%/getMe
echo.
echo.

echo [2/3] Testing getUpdates endpoint...
curl -s https://api.telegram.org/bot%BOT_TOKEN%/getUpdates
echo.
echo.

echo [3/3] Testing webhook info...
curl -s https://api.telegram.org/bot%BOT_TOKEN%/getWebhookInfo
echo.
echo.

echo ============================================
echo  Test complete!
echo ============================================
echo.
echo If you see {"ok":true,...} - bot token is valid
echo If you see {"ok":false,...} or error - check your token
echo.
pause
