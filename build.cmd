@echo off
setlocal
rem Build with the project's portable Windows toolchain. Arguments go to cmake --build.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build-windows.ps1" %*
exit /b %ERRORLEVEL%
