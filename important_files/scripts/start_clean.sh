#!/bin/bash
# Start Carrier Automation Tool (Clean Startup)

echo "Starting Carrier Automation Tool..."

# Kill any existing automation processes
pkill -f "api_server.py" 2>/dev/null
pkill -f "chat_server.py" 2>/dev/null

sleep 2

cd /OnRelay/skills/carrier-browser-automation

# Start Automation API (port 5000 - as configured in api_server.py)
echo "Starting Automation API..."
nohup python3 api_server.py > /tmp/automation_api.log 2>&1 &
API_PID=$!
echo $API_PID > /tmp/automation_api.pid

sleep 3

# Start Chat Server (port 8080 - needs to be different from AppsForte)
echo "Starting Chat Server..."
nohup python3 chat_server.py > /tmp/chat_server.log 2>&1 &
CHAT_PID=$!
echo $CHAT_PID > /tmp/chat_server.pid

sleep 3

echo ""
echo "✓ Carrier Automation Tool Started"
echo ""
echo "  PIDs: API=$API_PID, Chat=$CHAT_PID"
echo "  Logs: /tmp/automation_api.log, /tmp/chat_server.log"
echo ""
echo "  Local Access:"
echo "    Automation API: http://localhost:5000"
echo "    Chat Server:    http://localhost:8080"
echo ""
echo "  Tunnel Access (after restarting cloudflared):"
echo "    https://ai.appsscale.com/automationtest/"
echo ""
echo "  To stop: kill $API_PID $CHAT_PID"
