$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11 or newer is required."
}

python app.py --open-browser
