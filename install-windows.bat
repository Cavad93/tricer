@echo off
REM ========================================
REM NutriAI Bot - Windows Installation Script
REM ========================================
REM This script installs all dependencies on Windows without requiring Visual Studio Build Tools
REM Uses pre-compiled binary wheels for packages that normally require C++ compilation

echo ========================================
echo NutriAI Bot - Windows Installation
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip
    pause
    exit /b 1
)
echo.

echo [2/5] Installing packages that require binary wheels (pandas, numpy, matplotlib)...
echo This avoids C++ compilation which requires Visual Studio Build Tools
echo Note: For 32-bit Python, available versions may differ from requirements.txt
pip install pandas numpy matplotlib --only-binary :all: --upgrade
if errorlevel 1 (
    echo ERROR: Failed to install pandas/numpy/matplotlib
    echo Make sure you have Python 3.11 64-bit or 32-bit (binary wheels available)
    pause
    exit /b 1
)
echo.

echo [3/5] Installing greenlet and Pillow (binary wheels only)...
echo These packages also require compilation if installed from source
pip install greenlet Pillow --only-binary :all: --upgrade
if errorlevel 1 (
    echo ERROR: Failed to install greenlet/Pillow
    pause
    exit /b 1
)
echo.

echo [4/5] Installing remaining dependencies from requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements
    pause
    exit /b 1
)
echo.

echo [5/5] Verifying installation...
python -c "import pandas, numpy, matplotlib; print('SUCCESS: pandas, numpy, matplotlib imported successfully')"
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
