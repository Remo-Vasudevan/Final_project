param(
    [string]$PythonExe = ".\venv\Scripts\python.exe"
)

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python executable not found at $PythonExe. Create the virtual environment first with: python -m venv venv"
    exit 1
}

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r .\backend\requirements.txt

Write-Host "Backend base dependencies installed successfully."
Write-Host "Optional advanced OCR/ML packages are in backend\requirements-ml.txt"
