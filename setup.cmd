@echo off
setlocal
rem Run setup from this source-only checkout; asks a few questions, extracts assets from YOUR game files, builds and keeps a log.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\setup-wizard.ps1" %*
if errorlevel 1 (
  echo.
  echo Re-Nyastered setup did not finish. Read the message above. Your original game files have not been changed.
  pause
  exit /b 1
)
pause
