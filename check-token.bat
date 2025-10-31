@echo off
REM ============================================
REM Check .env Token Format
REM ============================================
echo.
echo ============================================
echo  Checking TELEGRAM_BOT_TOKEN format
echo ============================================
echo.

if not exist ".env" (
    echo [ERROR] .env file not found!
    pause
    exit /b 1
)

echo Checking token in .env file...
echo.

for /f "tokens=*" %%a in (.env) do (
    echo %%a | findstr /I "TELEGRAM_BOT_TOKEN" >nul
    if !errorlevel! equ 0 (
        set LINE=%%a
        echo Found line: !LINE!
        echo.

        REM Check for issues
        echo !LINE! | findstr " " >nul
        if !errorlevel! equ 0 (
            echo [WARNING] Token line contains spaces!
        )

        echo !LINE! | findstr "\"" >nul
        if !errorlevel! equ 0 (
            echo [WARNING] Token line contains quotes!
        )

        echo !LINE! | findstr "your_bot_token_here" >nul
        if !errorlevel! equ 0 (
            echo [ERROR] Token is still placeholder value!
            echo You need to replace it with your real bot token from @BotFather
        )
    )
)

echo.
echo ============================================
echo  Token format guide:
echo ============================================
echo.
echo CORRECT format:
echo   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
echo.
echo WRONG formats:
echo   TELEGRAM_BOT_TOKEN = 123456...  (spaces around =)
echo   TELEGRAM_BOT_TOKEN="123456..."  (quotes)
echo   TELEGRAM_BOT_TOKEN=your_bot...  (placeholder)
echo.
echo To get your bot token:
echo   1. Open Telegram
echo   2. Find @BotFather
echo   3. Send /mybots
echo   4. Select your bot
echo   5. Click "API Token"
echo   6. Copy the token and paste it in .env
echo.
pause
