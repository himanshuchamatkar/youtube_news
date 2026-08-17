# PowerShell script to package and copy the project to the USB drive E:\

$SourceDir = "D:\youtube_news"
$DestDir = "E:\youtube_news"

Write-Host "=== Packaging Stock Shorts Factory to USB Pendrive E:\ ===" -ForegroundColor Cyan

# 1. Create Target Directory Structure
if (!(Test-Path $DestDir)) {
    Write-Host "Creating target folder $DestDir..."
    New-Item -ItemType Directory -Path $DestDir | Out-Null
}

$SubDirs = @(
    "backend",
    "backend\app",
    "frontend",
    "frontend\dist",
    "scripts",
    "media",
    "media\rendered",
    "media\charts",
    "media\temp",
    "media\backgrounds",
    "ollama",
    "models"
)

foreach ($dir in $SubDirs) {
    $fullPath = Join-Path $DestDir $dir
    if (!(Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath | Out-Null
    }
}

# 2. Copy Backend Files (excluding venv, pycache, etc.)
Write-Host "Copying Backend..." -ForegroundColor Yellow
Copy-Item -Path "$SourceDir\backend\app\*" -Destination "$DestDir\backend\app" -Recurse -Force -Exclude @("*.pyc", "__pycache__")

# 3. Copy Scripts
Write-Host "Copying Helper Scripts..." -ForegroundColor Yellow
Copy-Item -Path "$SourceDir\scripts\*" -Destination "$DestDir\scripts" -Recurse -Force

# 4. Copy Precompiled Frontend Static Build
Write-Host "Copying Static Frontend Build..." -ForegroundColor Yellow
Copy-Item -Path "$SourceDir\frontend\dist\*" -Destination "$DestDir\frontend\dist" -Recurse -Force

# 5. Copy Core Configs & Database
Write-Host "Copying local database and environment config..." -ForegroundColor Yellow
if (Test-Path "$SourceDir\factory.db") {
    Copy-Item -Path "$SourceDir\factory.db" -Destination "$DestDir\factory.db" -Force
}
if (Test-Path "$SourceDir\.env") {
    Copy-Item -Path "$SourceDir\.env" -Destination "$DestDir\.env" -Force
}

# 6. Copy local Ollama installation (making it portable)
$OllamaSrc = "C:\Users\janhv\AppData\Local\Programs\Ollama"
$OllamaDst = "$DestDir\ollama"
if (Test-Path $OllamaSrc) {
    if ((Get-ChildItem $OllamaDst).Count -eq 0) {
        Write-Host "Copying Ollama portable binaries..." -ForegroundColor Yellow
        Copy-Item -Path "$OllamaSrc\*" -Destination $OllamaDst -Recurse -Force -Exclude @("unins000.*")
    } else {
        Write-Host "Ollama binaries already present on USB drive. Skipping copy." -ForegroundColor Gray
    }
}

# 7. Copy Ollama Qwen models
$ModelsSrc = "C:\Users\janhv\.ollama\models"
$ModelsDst = "$DestDir\models"
if (Test-Path $ModelsSrc) {
    if ((Get-ChildItem $ModelsDst).Count -eq 0) {
        Write-Host "Copying Qwen model files (4.7 GB)..." -ForegroundColor Yellow
        Copy-Item -Path "$ModelsSrc\*" -Destination $ModelsDst -Recurse -Force
    } else {
        Write-Host "Qwen models already present on USB drive. Skipping copy." -ForegroundColor Gray
    }
}

# 8. Create Double-Click run.bat Launcher on USB
Write-Host "Creating run.bat launcher..." -ForegroundColor Yellow
$BatchContent = @"
@echo off
title Stock Shorts Factory Launcher
echo ==========================================================
echo Starting Indian Stock Market Daily Shorts Factory from USB...
echo ==========================================================
cd /d "%~dp0"

:: Start local Ollama if it exists on USB
if exist "%~dp0ollama\ollama.exe" (
    echo Starting portable Ollama from USB...
    set OLLAMA_MODELS=%~dp0models
    start "" "%~dp0ollama\ollama.exe" serve
    timeout /t 5
) else (
    :: Check if Ollama is running globally on the host PC
    tasklist /FI "IMAGENAME eq ollama app.exe" 2>NUL | find /I /N "ollama app.exe" >NUL
    if "%ERRORLEVEL%"=="0" (
        echo Ollama is running on host PC.
    ) else (
        echo [WARNING] Ollama is not running! Checking if installed...
        if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama app.exe" (
            echo Starting installed Ollama on host...
            start "" "C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama app.exe"
            timeout /t 5
        ) else (
            echo [ERROR] Ollama is not running and not installed on this host PC!
            echo Please install Ollama from https://ollama.com to use local Qwen LLM.
            echo Alternatively, configure a valid Gemini API Key in the Settings dashboard.
            pause
        )
    )
)

:: Start FastAPI Python Server (which also hosts the compiled React frontend)
echo Starting Backend Web Server on http://localhost:8000 ...
start "" cmd /c "python -m uvicorn backend.app.main:app --port 8000"

:: Wait for startup and open browser dashboard
timeout /t 3
start http://localhost:8000
echo Shorts Factory Started Successfully!
pause
"@

$BatchContent | Out-File -FilePath "$DestDir\run.bat" -Encoding ascii -Force

Write-Host "=== Packaging Completed Successfully! ===" -ForegroundColor Green
Write-Host "You can now go to E:\youtube_news and run the application via run.bat!" -ForegroundColor Green
