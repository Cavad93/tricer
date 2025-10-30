@echo off
REM ========================================
REM NutriAI Bot - Windows Installation Script (Simplified)
REM ========================================

echo ========================================
echo NutriAI Bot - Windows Installation
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.11 64-bit from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo IMPORTANT: This script requires Python 3.11 64-bit
echo Make sure you installed 64-bit version, not 32-bit!
echo.
echo If you have 32-bit Python, download 64-bit from:
echo https://www.python.org/downloads/release/python-3119/
echo.
pause

echo [1/5] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip
    pause
    exit /b 1
)
echo.

echo [2/5] Installing pandas, numpy, matplotlib...
pip install pandas numpy matplotlib --only-binary=:all: --upgrade
if errorlevel 1 (
    echo ERROR: Failed to install pandas/numpy/matplotlib
    pause
    exit /b 1
)
echo.

echo [3/5] Installing Pillow...
pip install Pillow --only-binary=:all: --upgrade
if errorlevel 1 (
    echo ERROR: Failed to install Pillow
    pause
    exit /b 1
)
echo.

echo [4/5] Installing remaining dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements
    pause
    exit /b 1
)
echo.

echo [5/5] Verifying installation...
python -c "import pandas, numpy, matplotlib; print('SUCCESS: All packages imported')"
if errorlevel 1 (
    echo WARNING: Package verification failed
    pause
    exit /b 1
)
echo.

echo ========================================
echo Installation completed successfully!
echo ========================================
echo.
echo Next steps:
echo 1. Copy .env.example to .env
echo 2. Configure your .env file with API keys
echo 3. Run: python init_db.py
echo 4. Run: python -m app.bot.main
echo.
pause
