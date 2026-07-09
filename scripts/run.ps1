# Launch SnipOCR (creates venv on first run if missing)
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r requirements.txt
}

Write-Host "Starting SnipOCR..."
& $VenvPython main.py
