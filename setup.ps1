# Resume Builder — first-time setup
# Usage: .\setup.ps1

Write-Host "Setting up Resume Builder..." -ForegroundColor Green
Write-Host ""

# Python deps
Write-Host "Installing Python dependencies..."
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ pip install failed. Make sure Python 3.9+ is installed." -ForegroundColor Red
    exit 1
}

# Playwright Chromium
Write-Host ""
Write-Host "Installing Playwright Chromium (for PDF generation)..."
playwright install chromium
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Playwright install failed." -ForegroundColor Red
    exit 1
}

# Node deps
Write-Host ""
Write-Host "Installing Node dependencies..."
Set-Location web
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ npm install failed. Make sure Node.js 18+ is installed." -ForegroundColor Red
    Set-Location ..
    exit 1
}
Set-Location ..

Write-Host ""
Write-Host "✅ Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Set your API key:"
Write-Host "     `$env:ANTHROPIC_API_KEY = 'your-key-here'" -ForegroundColor Yellow
Write-Host "  2. Run: .\start.ps1"
