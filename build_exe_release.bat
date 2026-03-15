@echo off
title Blender Batch Builder
echo ---------------------------------------
echo Starting Build Process (PyInstaller)
echo ---------------------------------------
echo.
REM Check if pyinstaller is installed
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: PyInstaller is not installed!
    echo Please run: pip install pyinstaller
    pause
    exit /b
)

REM Ensure the application is not running to avoid PermissionError
taskkill /f /im Rbatch.exe >nul 2>&1

echo Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Rbatch.spec del /q Rbatch.spec
if exist __pycache__ rmdir /s /q __pycache__

echo Building Executable...
pyinstaller --noconfirm --onefile --windowed --clean ^
    --icon="icons\app_icon.ico" ^
    --add-data "languages;languages" ^
    --add-data "icons;icons" ^
    --hidden-import PySide6.QtSvg ^
    blender_batch.py

if %errorlevel% neq 0 (
    echo.
    echo Build Failed!
    pause
) else (
    echo.
    echo Build Successful! Your EXE is in the 'dist' folder.
    echo Note: You can now share the single EXE file.
    pause
)
