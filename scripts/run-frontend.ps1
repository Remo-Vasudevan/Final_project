param(
    [int]$Port = 4173,
    [string]$ApiOrigin = "http://127.0.0.1:8001"
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"

Push-Location $frontendRoot
try {
    $env:API_ORIGIN = $ApiOrigin
    npm run dev -- --port $Port
}
finally {
    Remove-Item Env:API_ORIGIN -ErrorAction SilentlyContinue
    Pop-Location
}
