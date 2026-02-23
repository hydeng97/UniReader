@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ====================================================
echo UniReader Build Script for Windows
echo ====================================================
echo.

if "%1"=="--clean" (
    echo Cleaning build directories...
    if exist build rmdir /s /q build
    if exist dist rmdir /s /q dist
    for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
    echo Clean completed.
    echo.
)

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11+
    exit /b 1
)

echo Checking PyInstaller...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Building UniReader...
python -m PyInstaller UniReader.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    exit /b 1
)

echo.
echo Copying additional files...
copy config.yaml.template dist\UniReader\ >nul
copy README.md dist\UniReader\ >nul
copy GUIDE.md dist\UniReader\ >nul

if not exist dist\UniReader\data\papers mkdir dist\UniReader\data\papers

if not exist dist\UniReader\static mkdir dist\UniReader\static
copy static\*.* dist\UniReader\static\ >nul

echo.
echo ====================================================
echo Build completed successfully!
echo Output: %CD%\dist\UniReader
echo ====================================================
echo.
echo To run: dist\UniReader\UniReader.exe
echo.

pause
