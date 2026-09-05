@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\bootstrap.ps1" %*
exit /b %errorlevel%
