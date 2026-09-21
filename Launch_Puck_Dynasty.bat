@echo off
echo ========================================
echo    PUCK DYNASTY - Hockey Manager
echo         Beta Version Launch
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    echo.
    pause
    exit /b 1
)

echo Starting Puck Dynasty...
echo.

REM Launch the game
python main.py

REM If there was an error, pause to see it
if errorlevel 1 (
    echo.
    echo An error occurred while launching the game.
    pause
)
