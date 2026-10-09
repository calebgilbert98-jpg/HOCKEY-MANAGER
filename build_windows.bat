@echo off
REM Puck Dynasty Native - Local Windows Build Script
REM Run this on your Windows PC to build without waiting for GitHub Actions.
REM
REM Prerequisites: Python 3.11 installed and on PATH
REM
REM Usage: build_windows.bat

echo === Puck Dynasty Native Local Build ===
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found on PATH. Install Python 3.11 from python.org
    pause
    exit /b 1
)

echo [1/4] Checking dependencies...
python -c "import PySide6; print('PySide6 OK')" 2>nul
if errorlevel 1 (
    echo   PySide6 not found, installing...
    echo   Removing any broken PySide6 install...
    python -m pip uninstall --quiet -y PySide6 PySide6-Addons PySide6-Essentials 2>nul
    echo   Installing pinned versions...
    python -m pip install --quiet --force-reinstall --no-cache-dir PySide6==6.12.0 pyinstaller==6.22.3 Pillow==11.0.0
    if errorlevel 1 (
        echo ERROR: pip install failed
        echo.
        echo If pip is broken, run this in Command Prompt first:
        echo   python -m ensurepip --upgrade
        echo Then try again.
        pause
        exit /b 1
    )
) else (
    echo   PySide6 already installed, skipping pip install.
)

echo [2/4] Running PyInstaller...
pyinstaller --clean --noconfirm puck_dynasty_native.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed
    pause
    exit /b 1
)

echo [3/4] Verifying bundle...
if not exist "dist\PuckDynasty\PuckDynasty.exe" (
    echo ERROR: PuckDynasty.exe not found in dist\PuckDynasty\
    pause
    exit /b 1
)

echo [4/4] Build complete!
echo.
echo   EXE: %CD%\dist\PuckDynasty\PuckDynasty.exe
echo.
echo   Run it to test. If it boots, the build is good.
echo.
pause
