param(
    [string]$PythonExe = "",
    [switch]$BaseOnly
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
    Write-Error "Python executable not found. Create a virtual environment first with: python -m venv venv"
    exit 1
}

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & $ResolvedPythonExe -m pip install --upgrade pip
    & $ResolvedPythonExe -m pip install -r .\backend\requirements.txt

    if (-not $BaseOnly) {
        & $ResolvedPythonExe -m pip install -r .\backend\requirements-ml.txt
    }
}
finally {
    Pop-Location
}

if ($BaseOnly) {
    Write-Host "Backend base dependencies installed successfully."
    Write-Host "Optional OCR/ML packages are available in backend\requirements-ml.txt"
}
else {
    Write-Host "Backend dependencies installed successfully, including OCR/ML support."
}

if (Test-PythonModule -PythonPath $ResolvedPythonExe -ModuleName "easyocr") {
    Write-Host "OCR engine check passed: easyocr is available."
}
else {
    Write-Warning "OCR engine check failed: easyocr is not available in the selected environment."
}
