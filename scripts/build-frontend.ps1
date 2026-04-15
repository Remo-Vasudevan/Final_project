$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"

Push-Location $frontendRoot
try {
    npm run build
}
finally {
    Pop-Location
}
