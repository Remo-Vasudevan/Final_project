param(
    [int]$Port = 4173
)

Push-Location .\frontend
try {
    npm run dev -- --port $Port
}
finally {
    Pop-Location
}
