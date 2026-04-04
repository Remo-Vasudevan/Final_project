param(
    [int]$Port = 8001,
    [string]$PythonExe = ".\venv\Scripts\python.exe"
)

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python executable not found at $PythonExe. Create and set up the virtual environment first."
    exit 1
}

& $PythonExe -m uvicorn backend.main:app --host 127.0.0.1 --port $Port --reload
