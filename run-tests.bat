@echo off
REM ============================================
REM NutriAI Bot - Comprehensive Testing Suite
REM ============================================
echo.
echo ============================================
echo  NutriAI Bot - Testing Suite
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Install test dependencies if needed
echo [INFO] Checking test dependencies...
pip show pytest >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing pytest...
    pip install pytest pytest-asyncio >nul 2>&1
)

echo.
echo ============================================
echo  Running comprehensive tests...
echo ============================================
echo.

REM Run comprehensive test suite
python test_bot.py

set TEST_EXIT_CODE=%errorlevel%

echo.
echo ============================================

if %TEST_EXIT_CODE% equ 0 (
    echo  All tests PASSED! Bot is ready to run
) else if %TEST_EXIT_CODE% equ 1 (
    echo  Some non-critical tests failed
) else (
    echo  Critical tests FAILED! Check errors above
)

echo ============================================
echo.
pause
exit /b %TEST_EXIT_CODE%
