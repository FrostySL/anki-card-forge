@echo off
rem Use forge.ps1 directly in PowerShell for literal HTML and shell metacharacters.
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\bootstrap.ps1" %*
exit /b %errorlevel%
