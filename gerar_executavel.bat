@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Preparando o executavel do EPROC para Windows...
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if errorlevel 1 (
    python -m venv .venv
  ) else (
    py -3 -m venv .venv
  )
  if errorlevel 1 goto erro
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-build.txt
if errorlevel 1 goto erro
".venv\Scripts\python.exe" gerar_executavel.py
if errorlevel 1 goto erro
echo.
echo Construcao concluida. A pasta e o ZIP estao em dist.
echo Use abrir_ultima_versao.bat para abrir a versao recem-gerada.
echo Encerre o programa anterior antes de abrir a versao nova.
explorer "%~dp0dist"
pause
exit /b 0
:erro
echo.
echo Nao foi possivel gerar o executavel. Copie a mensagem de erro acima.
pause
exit /b 1
