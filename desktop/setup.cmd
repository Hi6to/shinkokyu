@echo off
rem Shinkokyu desktop: first-time setup (installs parts and makes desktop shortcuts). See setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
pause
