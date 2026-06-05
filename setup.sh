#!/bin/bash

# Resume Builder — first-time setup
# Usage: ./setup.sh

echo "Setting up Resume Builder..."
echo ""

# Python deps
echo "Installing Python dependencies..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
  echo "❌ pip install failed. Make sure Python 3.9+ and pip are installed."
  exit 1
fi

# Playwright Chromium
echo ""
echo "Installing Playwright Chromium (for PDF generation)..."
playwright install chromium
if [ $? -ne 0 ]; then
  echo "❌ Playwright install failed."
  exit 1
fi

# Node deps
echo ""
echo "Installing Node dependencies..."
cd web && npm install
if [ $? -ne 0 ]; then
  echo "❌ npm install failed. Make sure Node.js 18+ is installed."
  exit 1
fi
cd ..

echo ""
echo "✅ Setup complete."
echo ""
echo "Next steps:"
echo "  1. Set your API key: export ANTHROPIC_API_KEY=your-key-here"
echo "  2. Run: ./start.sh"
