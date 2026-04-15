param(
    [int]$Port = 8001,
    [string]$PythonExe = "",
    [switch]$Reload
)

function Resolve-PythonExe {
    param([string]$RequestedPath)

    $candidates = @()

    if ($RequestedPath) {
        $candidates += $RequestedPath
    }

    if ($env:VIRTUAL_ENV) {
        $candidates += (Join-Path $env:VIRTUAL_ENV "Scripts\python.exe")
    }

    $repoRoot = Split-Path -Parent $PSScriptRoot
    $workspaceRoot = Split-Path -Parent $repoRoot
    $backendRoot = Join-Path $repoRoot "backend"
    $candidates += (Join-Path $repoRoot "venv\Scripts\python.exe")
    $candidates += (Join-Path $repoRoot ".venv\Scripts\python.exe")
    $candidates += (Join-Path $backendRoot "venv\Scripts\python.exe")
    $candidates += (Join-Path $backendRoot ".venv\Scripts\python.exe")
    $candidates += (Join-Path $workspaceRoot "venv\Scripts\python.exe")
    $candidates += (Join-Path $workspaceRoot ".venv\Scripts\python.exe")

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    return $null
}

function Test-PythonModule {
    param(
        [string]$PythonPath,
        [string]$ModuleName
    )

    if (-not $PythonPath -or -not (Test-Path $PythonPath)) {
        return $false
    }

    & $PythonPath -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('$ModuleName') else 1)" *> $null
    return ($LASTEXITCODE -eq 0)
}

$ResolvedPythonExe = Resolve-PythonExe -RequestedPath $PythonExe

if (-not $ResolvedPythonExe) {
    Write-Error "Python executable not found. Create a virtual environment and install backend dependencies first."
    exit 1
}

if (-not (Test-PythonModule -PythonPath $ResolvedPythonExe -ModuleName "easyocr")) {
    Write-Warning "The selected Python environment does not have easyocr installed."
    Write-Warning "Run .\scripts\setup-backend.ps1 before starting the backend if OCR output is empty."
}

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $uvicornArgs = @(
        "-m", "uvicorn",
        "backend.main:app",
        "--host", "127.0.0.1",
        "--port", $Port
    )

    if ($Reload) {
        $uvicornArgs += "--reload"
    }

    & $ResolvedPythonExe @uvicornArgs
}
finally {
    Pop-Location
}
