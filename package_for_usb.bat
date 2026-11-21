@echo off
title Package Stock Shorts Factory for USB
echo ======================================================================
echo Packaging Stock Shorts Factory for Standalone USB / Any PC...
echo ======================================================================
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\pack_to_usb.ps1"
pause
