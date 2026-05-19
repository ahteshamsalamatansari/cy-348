# Carrier Automation Chat Interface - Setup Guide

## Overview

This guide walks you through setting up the AI-powered chat interface for the Carrier Automation tool, accessible via Cloudflare tunnel at `ai.appsscale.com/automationtest`.

---

## Quick Start

### 1. Start All Services

```bash
cd /OnRelay/skills/carrier-browser-automation
./start_chat.sh
```

This will:
- Start the Automation API server (port 5000)
- Start the Chat server (port 8080)
- Display access instructions

### 2. Test Locally

Open your browser to:
```
http://localhost:8080
```

You should see the chat interface with connection status indicators.

---

## Cloudflare Tunnel Setup (for ai.appsscale.com)

### Option A: Quick Tunnel (Temporary URL)

```bash
# Install cloudflared (if not installed)
# Windows: https://github.com/cloudflare/cloudflare/releases/latest
# Linux:
wget https://github.com/cloudflare/cloudflare/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Start tunnel
cloudflared tunnel --url http://localhost:8080
```

This gives you a temporary `*.trycloudflare.com` URL.

### Option B: Custom Subdomain (ai.appsscale.com/automationtest)

**Prerequisites:**
- Cloudflare account with `ai.appsscale.com` domain
- `cloudflared` installed

**Step 1: Create Tunnel**

```bash
cloudflared tunnel create carrier-automation
```

Save the tunnel credentials that are displayed.

**Step 2: Configure Tunnel**

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <your-tunnel-id>
credentials-file: /home/youruser/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: ai.appsscale.com
    service: http://localhost:8080
    path: /automationtest/*
  - service: http_status:404
```

**Step 3: Run Tunnel**

```bash
cloudflared tunnel run
```

**Step 4: Configure DNS**

In Cloudflare Dashboard:
1. Go to DNS > Records
2. Add CNAME: `automationtest` -> `<your-tunnel-id>.cfargotunnel.com`

**Access:** `https://ai.appsscale.com/automationtest`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  User Browser (ai.appsscale.com/automationtest)            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Cloudflare Tunnel (HTTPS)                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Chat Server (Port 8080)                                    │
│  - Serves HTML chat interface                               │
│  - Handles CORS proxying                                   │
│  - Proxies to Automation API                               │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
┌───────────────────────────┐  ┌──────────────────────────┐
│  Automation API (5000)    │  │  LM Studio API           │
│  - Browser automation     │  │  - Qwen 3 53B model      │
│  - Form analysis          │  │  - Processes chat        │
│  - Form filling           │  │  - Generates actions     │
└───────────────────────────┘  └──────────────────────────┘
                │
                ▼
┌───────────────────────────┐
│  carrier.relayondemand.com│
│  - Login                  │
│  - Forms                  │
│  - Dispatch orders        │
└───────────────────────────┘
```

---

## Configuration

### Chat Interface Settings

The chat interface has a config panel (click ⚙️):

| Setting | Default | Description |
|---------|---------|-------------|
| LM Studio API | `https://api.appsscale.com/v1/chat/completions` | Your LM Studio endpoint |
| Model Name | `qwen3-coder-next-reap-40b-a3b` | Model to use |
| Automation API | `http://localhost:5000` | Automation API endpoint |

### Environment Variables (Optional)

```bash
# LM Studio Configuration
export LM_STUDIO_API="https://api.appsscale.com/v1/chat/completions"
export MODEL_NAME="qwen3-coder-next-reap-40b-a3b"

# Automation Configuration
export AUTOMATION_API="http://localhost:5000"
export CARRIER_USERNAME="apitest@test.com"
export CARRIER_PASSWORD="test123"
```

---

## Troubleshooting

### Chat Interface Not Loading

**Check servers:**
```bash
curl http://localhost:8080/api/health
curl http://localhost:5000/health
```

**View logs:**
```bash
tail -f /tmp/chat_server.log
tail -f /tmp/automation_api.log
```

### LM Studio Not Connecting

1. Verify LM Studio is running on Windows
2. Check the API endpoint in config
3. Ensure CORS is enabled in LM Studio settings

### Automation API Errors

1. Check browser is logged in:
   ```bash
   curl http://localhost:5000/api/analyze
   ```

2. Check credentials:
   ```bash
   echo $CARRIER_USERNAME
   echo $CARRIER_PASSWORD
   ```

### Cloudflare Tunnel Issues

**Tunnel not starting:**
```bash
# Check if cloudflared is installed
cloudflared --version

# Check if port 8080 is accessible
curl http://localhost:8080
```

**DNS not resolving:**
- Verify DNS records in Cloudflare Dashboard
- Check tunnel is running: `cloudflared tunnel list`

---

## Usage Examples

### Example 1: Analyze Current Page

**User:** "Analyze the current page"

**AI:**
- Calls `analyze` tool
- Returns form structure
- Explains what fields are available

### Example 2: Fill Form with Data

**User:** "Fill the form with address: 123 Main St"

**AI:**
- Analyzes form to find address field
- Calls `fill` tool with data
- Confirms success

### Example 3: Navigate and Fill

**User:** "Go to dispatch page and create a new order"

**AI:**
- Calls `navigate` tool
- Analyzes new page
- Asks for order details
- Fills the form

---

## Security Notes

1. **Credentials**: Stored in environment variables, never hardcoded
2. **CORS**: Chat server acts as proxy to avoid CORS issues
3. **HTTPS**: Use Cloudflare tunnel for encrypted access
4. **Authentication**: Add authentication to chat server for production use

---

## Advanced: Production Deployment

### Add Authentication

```python
# In chat_server.py
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    return username == 'admin' and password == 'your_secure_password'

@app.route('/')
@auth.login_required
def index():
    return send_from_directory('.', 'automation_chat.html')
```

### Use Reverse Proxy (Nginx)

```nginx
location /automationtest {
    proxy_pass http://localhost:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### SSL/TLS

Cloudflare tunnel automatically provides:
- Free SSL certificates
- DDoS protection
- Global CDN

---

## Support

For issues or questions:
- Check logs in `/tmp/chat_server.log` and `/tmp/automation_api.log`
- Review `TEST_RESULTS.md` for model integration test results
- See `README.md` for general tool documentation

---

## File Locations

| File | Location |
|------|----------|
| Chat Interface | `/OnRelay/skills/carrier-browser-automation/automation_chat.html` |
| Chat Server | `/OnRelay/skills/carrier-browser-automation/chat_server.py` |
| Startup Script | `/OnRelay/skills/carrier-browser-automation/start_chat.sh` |
| Automation API | `/OnRelay/skills/carrier-browser-automation/api_server.py` |
| Logs | `/tmp/chat_server.log`, `/tmp/automation_api.log` |
