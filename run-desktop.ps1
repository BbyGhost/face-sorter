Set-Location $PSScriptRoot
if (Test-Path .\.venv311\Scripts\python.exe) {
    & .\.venv311\Scripts\python.exe .\launcher_v4.py
} else {
    Write-Host "Python 3.11 setup is required first." -ForegroundColor Yellow
}
