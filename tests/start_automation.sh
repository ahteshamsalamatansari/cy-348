#!/bin/bash
# Start Carrier Automation Tool on separate ports to avoid conflicts

echo "Starting Carrier Automation Tool..."

# Kill any existing automation processes
pkill -f "api_server.py" 2>/dev/null
pkill -f "chat_server.py" 2>/dev/null

sleep 2

# Export environment variables for new ports
export AUTOMATION_API_PORT=9500
export CHAT_SERVER_PORT=9800

cd /OnRelay/skills/carrier-browser-automation

# Start Automation API on port 9500
echo "Starting Automation API on port 9500..."
nohup python3 -c "
from api_server import app
app.run(host='0.0.0.0', port=9500, debug=False)
" > /tmp/automation_api.log 2>&1 &
API_PID=$!

sleep 3

# Start Chat Server on port 9800
echo "Starting Chat Server on port 9800..."
nohup python3 -c "
from chat_server import app
app.run(host='0.0.0.0', port=9800, debug=False)
" > /tmp/chat_server.log 2>&1 &
CHAT_PID=$!

# Start Local Filter Model on port 9901
echo "Starting Local Filter Model on port 9901..."
nohup python3 runs.py > /tmp/filter_model.log 2>&1 &
FILTER_PID=$!

# Save PIDs
echo $API_PID > /tmp/automation_api.pid
echo $CHAT_PID > /tmp/chat_server.pid
echo $FILTER_PID > /tmp/filter_model.pid

echo ""
echo "✓ Carrier Automation Tool Started"
echo ""
echo "  Automation API: http://localhost:9500"
echo "  Chat Server:    http://localhost:9800"
echo "  Filter Model:   http://localhost:9901"
echo "  Tunnel Access:  https://ai.appsscale.com/automationtest/"
echo ""
echo "  To stop: kill $API_PID $CHAT_PID $FILTER_PID"
