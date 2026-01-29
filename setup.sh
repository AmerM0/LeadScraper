#!/bin/bash

# Quick Start Script for Lead Generation Tool
# This script automates the setup process

set -e  # Exit on error

echo "🎯 Lead Generation Tool - Quick Start"
echo "======================================"
echo ""

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Create virtual environment
echo ""
echo "🔧 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright
echo ""
echo "🎭 Installing Playwright browsers..."
playwright install chromium
echo "Installing Playwright system dependencies..."
playwright install-deps chromium

# Create .env if it doesn't exist
echo ""
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "✓ Created .env file (please add your OPENAI_API_KEY if needed)"
else
    echo "✓ .env file already exists"
fi

# Create static directory
mkdir -p static

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run: python main.py"
echo "  3. Open browser: http://localhost:8000"
echo ""
echo "Or use Docker:"
echo "  docker-compose up --build"
echo ""
