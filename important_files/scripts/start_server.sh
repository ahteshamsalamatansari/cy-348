#!/bin/bash
# Carrier Browser Automation - API Server Startup Script

echo "============================================================"
echo "  Carrier Browser Automation API Server"
echo "  Starting on http://localhost:5000"
echo "============================================================"
echo ""

# Check if port 5000 is in use
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "Port 5000 is already in use. Killing existing process..."
    fuser -k 5000/tcp 2>/dev/null
    sleep 2
fi

# Change to script directory
cd "$(dirname "$0")"

# Start the API server
echo "Starting API server..."
python3 api_server.py
