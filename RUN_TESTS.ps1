$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

python -m unittest discover -s tests -p "test_*.py" -v
python scripts\run_gold_eval.py
python scripts\run_governance_corpus.py
python scripts\privacy_audit.py

if (Get-Command node -ErrorAction SilentlyContinue) {
    node --check web\app.js
} else {
    Write-Warning "Node.js was not found; the JavaScript syntax check was skipped."
}
