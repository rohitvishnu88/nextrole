# Resume Builder — start both servers
# Usage: .\start.ps1

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ python not found. Install Python 3.9+ and try again." -ForegroundColor Red
    exit 1
}

# Check Node
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "❌ node not found. Install Node.js 18+ and try again." -ForegroundColor Red
    exit 1
}

# Check API key
if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "❌ ANTHROPIC_API_KEY is not set. Set it and try again." -ForegroundColor Red
    Write-Host "   Run: `$env:ANTHROPIC_API_KEY = 'your-key-here'" -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting Resume Builder..." -ForegroundColor Green
Write-Host "  Backend  → http://localhost:8000"
Write-Host "  Frontend → http://localhost:3000"
Write-Host "  Press Ctrl+C to stop both."
Write-Host ""

# Start both processes
$backend  = Start-Process -FilePath "python" -ArgumentList "-m uvicorn a2a.server:app --port 8000" -PassThru -NoNewWindow
$frontend = Start-Process -FilePath "cmd" -ArgumentList "/c cd web && npm run dev" -PassThru -NoNewWindow

# Wait and clean up on Ctrl+C
try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    if (-not $backend.HasExited)  { Stop-Process -Id $backend.Id  -Force }
    if (-not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force }
    Write-Host "Stopped." -ForegroundColor Yellow
}
