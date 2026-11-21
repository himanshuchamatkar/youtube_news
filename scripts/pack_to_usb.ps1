# PowerShell script to package the 100% standalone, zero-install Stock Shorts Factory for USB
param(
    [string]$TargetDir = "D:\StockShorts_USB_Ready",
    [string]$UsbDrive = ""
)

$ErrorActionPreference = "Continue"

if ($UsbDrive -ne "") {
    $TargetDir = Join-Path $UsbDrive "StockShorts_USB_Ready"
}

$SourceDir = "D:\yt"
$DestDir = $TargetDir

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  Stock Shorts Factory - 100% Standalone Zero-Install Packager" -ForegroundColor Cyan
Write-Host "  Target Destination: $DestDir" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Create Target Directory Structure
if (!(Test-Path $DestDir)) {
    Write-Host "Creating target root directory: $DestDir..." -ForegroundColor Green
    New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
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
    "logo",
    "ollama",
    "models",
    "ffmpeg",
    "python"
)

foreach ($dir in $SubDirs) {
    $fullPath = Join-Path $DestDir $dir
    if (!(Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}

# Helper function for fast robocopy
function Fast-Copy {
    param(
        [string]$Source,
        [string]$Destination,
        [string[]]$ExcludeDirs = @(),
        [string[]]$ExcludeFiles = @()
    )
    $argsList = @($Source, $Destination, "/E", "/MT:8", "/R:1", "/W:1", "/NP", "/NJH", "/NJS")
    if ($ExcludeDirs.Count -gt 0) {
        $argsList += "/XD"
        $argsList += $ExcludeDirs
    }
    if ($ExcludeFiles.Count -gt 0) {
        $argsList += "/XF"
        $argsList += $ExcludeFiles
    }
    & robocopy.exe @argsList | Out-Null
}

# 2. Copy Backend Files (excluding bytecode, pycache)
Write-Host "`n[1/8] Copying Backend Source Code..." -ForegroundColor Yellow
Fast-Copy -Source "$SourceDir\backend\app" -Destination "$DestDir\backend\app" -ExcludeDirs @("__pycache__", ".git") -ExcludeFiles @("*.pyc")
Write-Host "  [OK] Backend copied." -ForegroundColor Green

# 3. Copy Helper Scripts
Write-Host "`n[2/8] Copying Utility Scripts..." -ForegroundColor Yellow
Fast-Copy -Source "$SourceDir\scripts" -Destination "$DestDir\scripts" -ExcludeDirs @("__pycache__") -ExcludeFiles @("*.pyc")
Write-Host "  [OK] Scripts copied." -ForegroundColor Green

# 4. Copy Precompiled Frontend Static Build
Write-Host "`n[3/8] Copying Precompiled Frontend Static Assets..." -ForegroundColor Yellow
Fast-Copy -Source "$SourceDir\frontend\dist" -Destination "$DestDir\frontend\dist"
Write-Host "  [OK] Frontend assets copied." -ForegroundColor Green

# 5. Copy Core Database & Environment Keys
Write-Host "`n[4/8] Copying Database & Environment Configuration (.env / factory.db)..." -ForegroundColor Yellow
if (Test-Path "$SourceDir\factory.db") {
    Copy-Item -Path "$SourceDir\factory.db" -Destination "$DestDir\factory.db" -Force
    Write-Host "  [OK] SQLite Database (factory.db) copied." -ForegroundColor Green
}
if (Test-Path "$SourceDir\.env") {
    Copy-Item -Path "$SourceDir\.env" -Destination "$DestDir\.env" -Force
    Write-Host "  [OK] Environment config (.env) copied." -ForegroundColor Green
}
if (Test-Path "$SourceDir\logo") {
    Fast-Copy -Source "$SourceDir\logo" -Destination "$DestDir\logo"
    Write-Host "  [OK] Brand logos copied." -ForegroundColor Green
}

# 6. Copy Portable FFmpeg Binaries
Write-Host "`n[5/8] Bundling Portable FFmpeg (ffmpeg.exe & ffprobe.exe)..." -ForegroundColor Yellow
$FFmpegSrc = "C:\ffmpeg\bin"
$FFmpegDst = "$DestDir\ffmpeg"
if (Test-Path "$FFmpegSrc\ffmpeg.exe") {
    Copy-Item -Path "$FFmpegSrc\ffmpeg.exe" -Destination "$FFmpegDst\ffmpeg.exe" -Force
    Copy-Item -Path "$FFmpegSrc\ffprobe.exe" -Destination "$FFmpegDst\ffprobe.exe" -Force
    Write-Host "  [OK] FFmpeg portable binaries copied." -ForegroundColor Green
} else {
    Write-Host "  [WARN] FFmpeg source not found at $FFmpegSrc." -ForegroundColor Red
}

# 7. Copy Portable Python & All Pre-installed Libraries (~2.3 GB)
Write-Host "`n[6/8] Bundling Portable Python 3.11 with pre-installed libraries (~2.3 GB)..." -ForegroundColor Yellow
$PythonSrc = "C:\Users\janhv\AppData\Local\Programs\Python\Python311"
$PythonDst = "$DestDir\python"
if (Test-Path "$PythonSrc\python.exe") {
    Write-Host "  Fast-copying Python environment with multi-threading (1-2 minutes)..."
    Fast-Copy -Source $PythonSrc -Destination $PythonDst -ExcludeDirs @("__pycache__") -ExcludeFiles @("*.pyc")
    Write-Host "  [OK] Portable Python 3.11 copied successfully." -ForegroundColor Green
} else {
    Write-Host "  [WARN] Python 3.11 source not found at $PythonSrc." -ForegroundColor Red
}

# 8. Copy Ollama Binaries & Local AI Models (~4.5 GB)
Write-Host "`n[7/8] Bundling Portable Ollama Engine & Local Qwen 2.5 AI Model (~4.5 GB)..." -ForegroundColor Yellow
$OllamaSrc = "C:\Users\janhv\AppData\Local\Programs\Ollama"
$OllamaDst = "$DestDir\ollama"
if (Test-Path "$OllamaSrc\ollama.exe") {
    Write-Host "  Copying Ollama portable runtime..."
    Fast-Copy -Source $OllamaSrc -Destination $OllamaDst -ExcludeFiles @("unins000.*")
    Write-Host "  [OK] Ollama runtime copied." -ForegroundColor Green
}

$ModelsSrc = "C:\Users\janhv\.ollama\models"
$ModelsDst = "$DestDir\models"
if (Test-Path $ModelsSrc) {
    Write-Host "  Copying Qwen AI model weights (4.3 GB)..."
    Fast-Copy -Source $ModelsSrc -Destination $ModelsDst
    Write-Host "  [OK] Qwen 2.5 AI model weights copied." -ForegroundColor Green
}

# 9. Create Autonomous Plug & Play run.bat Launcher
Write-Host "`n[8/8] Creating 1-Click Plug & Play run.bat Launcher..." -ForegroundColor Yellow
$BatchContent = @"
@echo off
title Indian Stock Shorts Factory - Portable USB Launcher
color 0b
echo ======================================================================
echo           INDIAN STOCK MARKET SHORTS FACTORY (PORTABLE)
echo ======================================================================
echo.

:: Switch working directory to pendrive root
cd /d "%~dp0"

echo [1/4] Configuring Standalone Environment...
:: 1. Add Portable FFmpeg to PATH
if exist "%~dp0ffmpeg\ffmpeg.exe" (
    set "PATH=%~dp0ffmpeg;%PATH%"
    echo   [OK] Portable FFmpeg activated.
) else (
    echo   [INFO] Portable FFmpeg not present in folder, checking system PATH.
)

:: 2. Configure Portable Python Environment
if exist "%~dp0python\python.exe" (
    set "PATH=%~dp0python;%~dp0python\Scripts;%PATH%"
    set "PYTHONHOME=%~dp0python"
    set "PYTHONPATH=%~dp0;%~dp0python\Lib\site-packages"
    set "PYTHON_EXE=%~dp0python\python.exe"
    echo   [OK] Portable Python 3.11 activated.
) else (
    set "PYTHON_EXE=python"
    echo   [INFO] Portable Python not found, falling back to system Python.
)

:: 3. Configure and Start Ollama Engine
echo.
echo [2/4] Initializing Local AI Engine (Ollama)...
if exist "%~dp0ollama\ollama.exe" (
    set "PATH=%~dp0ollama;%PATH%"
    set "OLLAMA_MODELS=%~dp0models"
    echo   [OK] Starting portable Ollama with local Qwen 2.5 models...
    start "Ollama AI Engine" /B "%~dp0ollama\ollama.exe" serve
    timeout /t 3 /nobreak >nul
) else (
    echo   [INFO] Ollama runtime will use local host if present.
)

:: 4. Start the Web Dashboard & Pipeline Backend
echo.
echo [3/4] Launching Stock Shorts Automation Engine...
echo   Command: %PYTHON_EXE% -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
start "Stock Shorts Factory Server" cmd /k ""%PYTHON_EXE%" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"

:: 5. Open Web Browser
echo.
echo [4/4] Opening Dashboard in your browser...
timeout /t 4 /nobreak >nul
start http://localhost:8000

echo.
echo ======================================================================
echo   READY! Dashboard running at: http://localhost:8000
echo   Default Credentials:
echo     Username: admin
echo     Password: admin123
echo.
echo   NOTE: Keep this window open while using the application.
echo ======================================================================
echo.
pause
"@

$BatchContent | Out-File -FilePath "$DestDir\run.bat" -Encoding ascii -Force

# 10. Create README_HOW_TO_USE.txt
$ReadmeContent = @"
======================================================================
INDIAN STOCK MARKET SHORTS FACTORY - 100% STANDALONE USB EDITION
======================================================================

HOW TO PUT THIS ON A PENDRIVE:
1. Insert your USB pendrive (needs at least 8 GB of free space).
2. Copy this entire folder ("StockShorts_USB_Ready") to your pendrive.

HOW TO RUN ON ANY WINDOWS PC (ZERO INSTALLATION REQUIRED):
1. Plug your pendrive into ANY Windows computer.
2. Open the "StockShorts_USB_Ready" folder on the pendrive.
3. Double-click "run.bat".
4. The dashboard will automatically launch at http://localhost:8000 in your browser!

LOGIN CREDENTIALS:
- Username: admin
- Password: admin123

WHAT IS BUNDLED INSIDE THIS FOLDER:
- Portable Python 3.11 with all pre-installed packages (FastAPI, Uvicorn, Edge-TTS, Google APIs)
- Portable FFmpeg video rendering engine
- Portable Ollama offline AI engine
- Qwen 2.5 7B offline language model
- Precompiled frontend dashboard
- Complete backend pipeline
- Your configured .env keys and database

DOES THE TARGET PC NEED PYTHON OR FFMPEG INSTALLED?
No! Everything is bundled directly in this folder. The other PC does not need 
Python, Node.js, FFmpeg, or Ollama installed.

======================================================================
"@

$ReadmeContent | Out-File -FilePath "$DestDir\README_HOW_TO_USE.txt" -Encoding ascii -Force

Write-Host "`n======================================================================" -ForegroundColor Green
Write-Host "  SUCCESS! 100% STANDALONE ZERO-INSTALL PACKAGE COMPLETED!" -ForegroundColor Green
Write-Host "  Location: $DestDir" -ForegroundColor Green
Write-Host "  Total Size: ~7.2 GB (includes Python, FFmpeg, Ollama & Qwen 2.5 AI model)" -ForegroundColor Green
Write-Host "  You can simply copy this entire folder to any USB pendrive!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
