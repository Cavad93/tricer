@echo off
REM ========================================
REM DejaVu Fonts Installation Script
REM ========================================
REM This script downloads and installs DejaVu fonts for PDF generation
REM Run as Administrator!

echo ========================================
echo DejaVu Fonts Installation
echo ========================================
echo.
echo This will install DejaVu fonts needed for PDF generation.
echo Russian text will display correctly in shopping lists and meal plans.
echo.
echo IMPORTANT: Run this script as Administrator!
echo.
pause

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Right-click the script and select "Run as administrator"
    pause
    exit /b 1
)

echo [1/5] Creating temporary directory...
if not exist temp_fonts mkdir temp_fonts
cd temp_fonts

echo [2/5] Downloading DejaVu fonts (version 2.37)...
curl -L -o dejavu-fonts.zip "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"
if errorlevel 1 (
    echo ERROR: Failed to download fonts
    echo Please check your internet connection
    cd ..
    rmdir /s /q temp_fonts
    pause
    exit /b 1
)

echo [3/5] Extracting fonts...
tar -xf dejavu-fonts.zip
if errorlevel 1 (
    echo ERROR: Failed to extract fonts
    cd ..
    rmdir /s /q temp_fonts
    pause
    exit /b 1
)

echo [4/5] Installing fonts to Windows Fonts directory...
copy "dejavu-fonts-ttf-2.37\ttf\DejaVuSans.ttf" "%SystemRoot%\Fonts\" >nul
copy "dejavu-fonts-ttf-2.37\ttf\DejaVuSans-Bold.ttf" "%SystemRoot%\Fonts\" >nul

if errorlevel 1 (
    echo WARNING: Failed to copy fonts to system directory
    echo Trying to create project fonts directory instead...
    cd ..
    if not exist fonts mkdir fonts
    copy "temp_fonts\dejavu-fonts-ttf-2.37\ttf\DejaVuSans.ttf" "fonts\" >nul
    copy "temp_fonts\dejavu-fonts-ttf-2.37\ttf\DejaVuSans-Bold.ttf" "fonts\" >nul
    echo Fonts installed to project directory: fonts\
    goto cleanup
)

echo [5/5] Registering fonts in Windows registry...
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" /v "DejaVu Sans (TrueType)" /t REG_SZ /d DejaVuSans.ttf /f >nul
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" /v "DejaVu Sans Bold (TrueType)" /t REG_SZ /d "DejaVuSans-Bold.ttf" /f >nul

:cleanup
echo.
echo Cleaning up...
cd ..
rmdir /s /q temp_fonts

echo.
echo ========================================
echo Installation completed successfully!
echo ========================================
echo.
echo Installed fonts:
echo - DejaVuSans.ttf
echo - DejaVuSans-Bold.ttf
echo.
echo Next steps:
echo 1. Restart the bot: python -m app.bot.main
echo 2. Generate a meal plan or shopping list
echo 3. Russian text should display correctly in PDF
echo.
pause
