$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv311"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
  Write-Host "Python 3.11 virtual environment not found: $venv" -ForegroundColor Red
  exit 1
}

Write-Host "Removing DirectML/CPU ONNX Runtime packages..." -ForegroundColor Yellow
& $python -m pip uninstall -y onnxruntime onnxruntime-directml onnxruntime-gpu

Write-Host "Installing ONNX Runtime CUDA 12.x + cuDNN..." -ForegroundColor Cyan
& $python -m pip install --upgrade "onnxruntime-gpu[cuda,cudnn]==1.26.0"

Write-Host "Verifying ONNX Runtime providers..." -ForegroundColor Cyan
& $python -c "import onnxruntime as ort; print('Providers:', ort.get_available_providers())"

Write-Host ""
Write-Host "GPU setup complete. Restart Face Sorter and select GPU only." -ForegroundColor Green
