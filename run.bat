@echo off
title Stock Shorts Factory Launcher
echo ==========================================================
echo Starting Indian Stock Market Daily Shorts Factory...
echo ==========================================================
cd /d "%~dp0"

:: Check if Ollama is running globally on the host PC
tasklist /FI "IMAGENAME eq ollama app.exe" 2>NUL | find /I /N "ollama app.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    echo [OK] Ollama is already running on host PC.
) else (
    tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe" >NUL
    if "%ERRORLEVEL%"=="0" (
        echo [OK] Ollama service is running.
    ) else (
        echo [INFO] Ollama is not running. Starting Ollama...
        if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama app.exe" (
            start "" "C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama app.exe"
            timeout /t 4 /nobreak >nul
        ) else (
            echo [WARNING] Ollama was not found in AppData. Trying default command...
            start "" ollama serve
            timeout /t 4 /nobreak >nul
        )
    )
)

:: Start FastAPI Python Server
echo Starting Backend Web Server on http://localhost:8000 ...
start "" cmd /k "python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"

:: Wait for backend to initialize
timeout /t 3 /nobreak >nul

:: Open browser dashboard
start http://localhost:8000
echo ==========================================================
echo Shorts Factory Dashboard launched at http://localhost:8000
echo ==========================================================
pause
