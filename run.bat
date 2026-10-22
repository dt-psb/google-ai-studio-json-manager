@echo off
title Google AI Studio - Prompt and Chunk Manager

echo ========================================================
echo   Google AI Studio - Prompt and Chunk Manager
echo ========================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [Notice] Python not found. Opening index.html in browser...
    start "" "index.html"
) else (
    echo [OK] Starting local API server with Python...
    echo Browser will open automatically. (To stop: Ctrl+C)
    echo.
    python server.py
)

pause