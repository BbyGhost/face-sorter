$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv311"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
  Write-Host "Python 3.11 virtual environment not found: $venv" -ForegroundColor Red
  exit 1
}

Write-Host "Removing conflicting ONNX Runtime packages..." -ForegroundColor Yellow
& $python -m pip uninstall -y onnxruntime onnxruntime-directml onnxruntime-gpu

Write-Host "Installing ONNX Runtime CUDA 12.8..." -ForegroundColor Cyan
& $python -m pip install --upgrade "onnxruntime-gpu==1.26.0"

Write-Host "Installing NVIDIA CUDA 12 runtime DLL packages..." -ForegroundColor Cyan
& $python -m pip install --upgrade "nvidia-cuda-runtime-cu12" "nvidia-cublas-cu12" "nvidia-cufft-cu12" "nvidia-curand-cu12" "nvidia-cusolver-cu12" "nvidia-cusparse-cu12" "nvidia-nvjitlink-cu12" "nvidia-cudnn-cu12==9.7.1.26"

Write-Host "Preloading and verifying CUDA DLLs..." -ForegroundColor Cyan
& $python -c "import onnxruntime as ort; print('ORT version:',ort.__version__); print('Preloading NVIDIA DLLs...'); ort.preload_dlls(directory=''); ort.print_debug_info(); print('Providers:',ort.get_available_providers()); assert 'CUDAExecutionProvider' in ort.get_available_providers(), 'CUDAExecutionProvider is unavailable'"

Write-Host ""
Write-Host "CUDA setup complete." -ForegroundColor Green
Write-Host "Restart Face Sorter and select GPU only." -ForegroundColor Green
