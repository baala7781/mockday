#!/bin/bash

# MockDay Backend - Local Development Start Script

set -e

echo "🚀 Starting MockDay Backend..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "📋 Copy env.example to .env and configure it:"
    echo "   cp env.example .env"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
elif [ -d "intervieu" ]; then
    echo "📦 Activating virtual environment (intervieu)..."
    source intervieu/bin/activate
else
    echo "⚠️  No virtual environment found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 Installing requirements..."
    pip install -r requirements.txt
fi

# Check if requirements are installed
if ! python -c "import uvicorn" 2>/dev/null; then
    echo "📦 Installing requirements..."
    pip install -r requirements.txt
fi

# Start the server
echo "🌟 Starting FastAPI server on http://localhost:8002"
echo ""
uvicorn interview_service.main:app --host 0.0.0.0 --port 8002 --reload

