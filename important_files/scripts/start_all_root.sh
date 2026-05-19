#!/bin/bash
# Start all services as root

echo "Starting AppsForte Services as root..."

# Start AppsForte AI Web Interface
cd /mnt/c/Users/appsf/Desktop/AppsForte-Cloudflared-Services/ai_webapp
sudo python3 app_with_auth.py &
AI_PID=$!
echo "AppsForte AI PID: $AI_PID"

sleep 5

# Start Carrier Automation
cd /OnRelay/skills/carrier-browser-automation
sudo python3 api_server.py &
API_PID=$!
echo "Automation API PID: $API_PID"

sleep 3

sudo python3 chat_server.py &
CHAT_PID=$!
echo "Chat Server PID: $CHAT_PID"

echo ""
echo "✓ All services started as root"
echo ""
echo "PIDs saved to /tmp/"
echo $AI_PID > /tmp/ai_webapp.pid
echo $API_PID > /tmp/automation_api.pid
echo $CHAT_PID > /tmp/chat_server.pid

echo ""
echo "Access URLs:"
echo "  AppsForte:     https://ai.appsscale.com/"
echo "  Automation:     https://ai.appsscale.com/automationtest/"
