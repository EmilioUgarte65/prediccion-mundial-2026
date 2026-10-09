# Prepara el proyecto en una PC nueva: entorno virtual local + dependencias + datos historicos.
# No instala nada global. Uso:  powershell -ExecutionPolicy Bypass -File .\instalar.ps1 [-Opcional]
param([switch]$Opcional)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Falta Python 3.11 o superior (https://www.python.org).' }
python --version

if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python -m pip install --upgrade pip
if ($Opcional) { & .\.venv\Scripts\python -m pip install -r requirements-opcional.txt }
else           { & .\.venv\Scripts\python -m pip install -r requirements.txt }

if (-not (Test-Path data_repo)) {
  Write-Host 'Clonando datos historicos (martj42/international_results) en data_repo/'
  git clone https://github.com/martj42/international_results.git data_repo
}

if (-not (Test-Path config\api_keys.json)) {
  Copy-Item config\api_keys.example.json config\api_keys.json
  Write-Host 'Se creo config\api_keys.json vacio: llenalo solo si vas a refrescar datos con fetch_all.py'
}

Write-Host 'Listo. Siguiente:  .venv\Scripts\python build.py   y luego   .venv\Scripts\python -m http.server 8000 --directory web'
