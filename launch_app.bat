@echo off
setlocal enabledelayedexpansion
title Google AI Studio Desktop App Launcher
cd /d "%~dp0"

set "LOGFILE=%~dp0launch_error.log"

echo ======================================================== > "%LOGFILE%"
echo [%DATE% %TIME%] Launching Google AI Studio Desktop App >> "%LOGFILE%"
echo ======================================================== >> "%LOGFILE%"

echo Searching for Python executable... >> "%LOGFILE%"

set "PY_EXE="

:: 1. Check Anaconda Python
if exist "C:\ProgramData\anaconda3\pythonw.exe" (
    set "PY_EXE=C:\ProgramData\anaconda3\pythonw.exe"
    goto :FOUND
)
if exist "C:\ProgramData\anaconda3\python.exe" (
    set "PY_EXE=C:\ProgramData\anaconda3\python.exe"
    goto :FOUND
)

:: 2. Check Python 3.12
if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
    goto :FOUND
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :FOUND
)

:: 3. Check system PATH pythonw / python
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('where pythonw') do (
        set "PY_EXE=%%i"
        goto :FOUND
    )
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('where python') do (
        set "PY_EXE=%%i"
        goto :FOUND
    )
)

:FOUND
if "%PY_EXE%"=="" (
    echo [ERROR] No Python installation found on system! >> "%LOGFILE%"
    echo [ERROR] Python not found! Please check launch_error.log
    pause
    exit /b 1
)

echo Selected Python: "%PY_EXE%" >> "%LOGFILE%"
echo Starting app.pyw ... >> "%LOGFILE%"

start "" "%PY_EXE%" "%~dp0app.pyw"

echo Launch command sent successfully. >> "%LOGFILE%"
exit /b 0
