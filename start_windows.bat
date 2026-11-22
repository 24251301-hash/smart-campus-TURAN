@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Smart Campus TURAN

echo ================================================
echo    SMART CAMPUS TURAN - LOCAL SERVER
echo ================================================
echo.

set "PYTHON_CMD="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)
if not defined PYTHON_CMD goto no_python

echo Python found:
%PYTHON_CMD% --version
echo.
if not exist "requirements.txt" goto missing_files
if not exist "server.py" goto missing_files

echo [1/2] Checking Python packages...
%PYTHON_CMD% -m pip --version >nul 2>&1
if errorlevel 1 goto no_pip
%PYTHON_CMD% -m pip install -r "requirements.txt"
if errorlevel 1 goto install_failed

echo.
echo [2/2] Starting local web application...
echo OPEN YOUR BROWSER: http://127.0.0.1:8000/
echo Keep this window open while using the site.
echo Stop server with Ctrl+C.
echo.
%PYTHON_CMD% "server.py"
echo.
echo Server stopped. Check the messages above if it did not start.
pause
exit /b 0

:no_python
echo ERROR: Python 3.10 or later is not installed or is not on PATH.
echo Download Python from: https://www.python.org/downloads/windows/
echo During installation check: Add python.exe to PATH
echo Then close this window and run start_windows.bat again.
pause
exit /b 1

:no_pip
echo ERROR: pip is not available for your Python interpreter.
echo Trying to repair pip...
%PYTHON_CMD% -m ensurepip --upgrade
if errorlevel 1 (
    echo Unable to repair pip. Try reinstalling Python with pip enabled.
    pause
    exit /b 1
)
echo Please run start_windows.bat again.
pause
exit /b 1

:missing_files
echo ERROR: Missing requirements.txt or server.py.
echo Extract the whole ZIP archive before running start_windows.bat.
pause
exit /b 1

:install_failed
echo ERROR: Unable to install the required Python packages.
echo Check your internet connection and Python version, then retry.
pause
exit /b 1
