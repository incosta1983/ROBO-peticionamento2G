@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Execute instalar.ps1 antes de iniciar a interface.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" interface.py
pause
