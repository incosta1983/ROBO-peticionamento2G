$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
py -3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível criar o ambiente Python. Instale Python 3.12 ou superior.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Falha na instalação das dependências.' }
& .\.venv\Scripts\python.exe -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Falha no download do navegador.' }
Write-Host 'Instalação concluída. Consulte README.md para validar a planilha e executar.'
