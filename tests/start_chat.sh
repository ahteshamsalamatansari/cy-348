#!/bin/bash
# Complete startup script for Carrier Automation Chat

echo "============================================================"
echo "  Carrier Automation Chat - Startup"
echo "============================================================"
echo ""

# Kill any existing processes
echo "Stopping any existing servers..."
pkill -f api_server.py 2>/dev/null
pkill -f chat_server.py 2>/dev/null
sleep 2

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if automation API is running, start if not
echo ""
echo "[1/3] Starting Automation API Server..."
nohup python3 api_server.py > /tmp/automation_api.log 2>&1 &
API_PID=$!
sleep 5

# Check if API is healthy
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo "    ✓ Automation API running (PID: $API_PID)"
else
    echo "    ✗ Automation API failed to start"
    echo "    Check log: tail -f /tmp/automation_api.log"
    exit 1
fi

# Start chat server
echo ""
echo "[2/3] Starting Chat Server..."
nohup python3 chat_server.py > /tmp/chat_server.log 2>&1 &
CHAT_PID=$!
sleep 3

# Check if chat server is healthy
if curl -s http://localhost:8080/api/health > /dev/null 2>&1; then
    echo "    ✓ Chat Server running (PID: $CHAT_PID)"
else
    echo "    ✗ Chat Server failed to start"
    echo "    Check log: tail -f /tmp/chat_server.log"
    exit 1
fi

# Save PIDs for later
echo $API_PID > /tmp/automation_api.pid
echo $CHAT_PID > /tmp/chat_server.pid

# Instructions
echo ""
echo "[3/3] Setup Complete!"
echo ""
echo "============================================================"
echo "  ACCESS METHODS"
echo "============================================================"
echo ""
echo "  Local Access:"
echo "    http://localhost:8080"
echo "    http://127.0.0.1:8080"
echo ""
echo "  Cloudflare Tunnel (to make accessible via ai.appsscale.com):"
echo ""
echo "    1. Install cloudflared:"
echo "       - Windows: https://github.com/cloudflare/cloudflare/releases/latest"
echo "       - Linux: wget https://github.com/cloudflare/cloudflare/releases/latest/download/cloudflared-linux-amd64.deb"
echo "                 sudo dpkg -i cloudflared-linux-amd64.deb"
echo ""
echo "    2. Create tunnel:"
echo "       cloudflared tunnel --url http://localhost:8080"
echo ""
echo "    3. Configure Cloudflare to use subdomain:"
echo "       cloudflared tunnel --url http://localhost:8080:automationtest@ai.appsscale.com"
echo ""
echo "============================================================"
echo "  SERVICE STATUS"
echo "============================================================"
echo ""
echo "  Automation API: http://localhost:5000"
echo "  Chat Interface: http://localhost:8080"
echo ""
echo "  PIDs saved to:"
echo "    - /tmp/automation_api.pid"
echo "    - /tmp/chat_server.pid"
echo ""
echo "  To stop all services:"
echo "    kill $(cat /tmp/automation_api.pid) $(cat /tmp/chat_server.pid)"
echo ""
echo "  To view logs:"
echo "    tail -f /tmp/automation_api.log"
echo "    tail -f /tmp/chat_server.log"
echo ""
echo "============================================================"
echo ""
echo "✓ Ready! Chat interface available at: http://localhost:8080"
echo ""
