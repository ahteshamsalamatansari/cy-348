# Quick Start: Carrier Automation Chat

## 🚀 Start Everything (One Command)

```bash
cd /OnRelay/skills/carrier-browser-automation
./start_chat.sh
```

Then open: **http://localhost:8080**

---

## 🌐 Access via Cloudflare Tunnel (ai.appsscale.com/automationtest)

### Step 1: Install cloudflared

**Windows:**
1. Download: https://github.com/cloudflare/cloudflare/releases/latest
2. Extract and add to PATH

**Linux:**
```bash
wget https://github.com/cloudflare/cloudflare/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

### Step 2: Start Tunnel

**Option A - Quick temporary URL:**
```bash
cloudflared tunnel --url http://localhost:8080
```
→ Gives you a `*.trycloudflare.com` URL

**Option B - Custom subdomain (ai.appsscale.com):**

First, configure tunnel in `~/.cloudflared/config.yml`:
```yaml
tunnel: <your-tunnel-id>
credentials-file: ~/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: ai.appsscale.com
    service: http://localhost:8080
    path: /automationtest/*
  - service: http_status:404
```

Then run:
```bash
cloudflared tunnel run
```

Access at: **https://ai.appsscale.com/automationtest**

---

## 📋 Test the Chat

### Example Conversations to Try:

**1. Analyze Form:**
```
You: "Analyze the current page"
AI: [Shows form structure with all fields]
```

**2. Fill Form:**
```
You: "Fill the form with start address: 123 Main St"
AI: [Fills the form and confirms]
```

**3. Screenshot:**
```
You: "Take a screenshot"
AI: [Takes screenshot and shows path]
```

---

## ✅ Status Indicators

| Status | Meaning |
|--------|---------|
| 🟢 Green | Connected and working |
| 🟡 Yellow | Testing/Loading |
| 🔴 Red | Not connected |

---

## 🛠️ Services Running

| Service | Port | Purpose |
|---------|------|---------|
| Automation API | 5000 | Browser automation |
| Chat Server | 8080 | Web interface + proxy |
| LM Studio | varies | AI model (Windows) |

---

## 📝 Current Page Info

The chat shows:
- **Current URL**: Which page you're on
- **Form Count**: How many fields detected
- **Refresh**: Click to re-analyze page

---

## 🔧 Troubleshooting

**Chat not loading:**
```bash
curl http://localhost:8080/api/health
```

**Automation not working:**
```bash
curl http://localhost:5000/api/analyze
```

**View logs:**
```bash
tail -f /tmp/chat_server.log
tail -f /tmp/automation_api.log
```

**Stop all services:**
```bash
kill $(cat /tmp/automation_api.pid) $(cat /tmp/chat_server.pid)
```

---

## 🎯 Quick Tips

1. **Start with "Analyze current page"** - See what's available
2. **Use the suggestion chips** - Click quick actions
3. **Provide specific values** - Helps the AI fill forms correctly
4. **Check status indicators** - Green = ready to use

---

## 📁 Files

| File | Purpose |
|------|---------|
| `automation_chat.html` | Chat interface |
| `chat_server.py` | Web server + proxy |
| `api_server.py` | Automation API |
| `start_chat.sh` | Start everything |
| `CHAT_SETUP_GUIDE.md` | Full documentation |

---

## 🔐 Default Credentials

- **Username**: `apitest@test.com`
- **Password**: `test123`
- **URL**: `https://carrier.relayondemand.com`

These are pre-configured in the automation tool.
