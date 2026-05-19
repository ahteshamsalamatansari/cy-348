# 🚀 Setup: ai.appsscale.com/automationtest

## Overview

Access the Carrier Automation Chat at: **https://ai.appsscale.com/automationtest/**

---

## ✅ Current Status

| Service | Status | Port |
|---------|--------|------|
| Automation API | ✅ Running | 5000 |
| Chat Server | ✅ Running | 8080 |
| WSL IP | 192.168.47.119 | - |

---

## 🌐 Cloudflare Tunnel Configuration

**Config File:** `C:\Users\appsf\.cloudflared\config.yml`

**Routing:**
```yaml
- hostname: ai.appsscale.com
  path: /automationtest/*
  service: http://192.168.47.119:8080
```

---

## 🔄 Restart Cloudflare Tunnel (Windows)

### Option 1: Using Batch Script

1. Open Command Prompt or PowerShell on Windows
2. Run:
   ```cmd
   C:\Users\appsf\Desktop\OnRelay\restart_cf_tunnel.bat
   ```

### Option 2: Manual Restart

```cmd
# 1. Kill existing tunnel
taskkill /F /IM cloudflared.exe

# 2. Start tunnel
"C:\Users\appsf\AppData\Local\cloudflared\cloudflared-windows-amd64.exe" tunnel run --config C:\Users\appsf\.cloudflared\config.yml
```

### Option 3: Run as Service (Recommended)

Install as Windows service:
```cmd
cloudflared service install
```

Then:
```cmd
net start cloudflared
```

---

## 🧪 Test Access

### 1. Test Local Access

```bash
curl http://localhost:8080/api/health
```

Should return:
```json
{"service":"Carrier Automation Chat Server","status":"healthy"}
```

### 2. Test from Windows

Open in browser:
```
http://192.168.47.119:8080
```

### 3. Test via Cloudflare Tunnel

Open in browser:
```
https://ai.appsscale.com/automationtest/
```

---

## 🔧 Troubleshooting

### Tunnel Not Working

**Check if cloudflared is running:**
```cmd
tasklist | findstr cloudflared
```

**Check tunnel logs:**
- View Cloudflare Dashboard: https://dash.cloudflare.com/
- Look for DNS settings for ai.appsscale.com

### Chat Not Loading

**1. Verify WSL services:**
```bash
curl http://localhost:8080/api/health
curl http://localhost:5000/health
```

**2. Check Windows can reach WSL:**
```cmd
curl http://192.168.47.119:8080/api/health
```

**3. Check firewall:**
- Windows Firewall allows port 8080
- WSL network is accessible

### Path Not Found Error

**1. Verify Cloudflare config:**
```yaml
path: /automationtest/*
service: http://192.168.47.119:8080
```

**2. Check order of rules:**
- More specific rules must come before general rules
- The `/automationtest/*` rule should be before the `ai.appsscale.com` rule

---

## 📱 Access URLs

| Method | URL |
|--------|-----|
| Local (WSL) | http://localhost:8080 |
| Local (Windows) | http://192.168.47.119:8080 |
| Via Tunnel | https://ai.appsscale.com/automationtest/ |
| Direct | https://ai.appsscale.com/automationtest |

---

## 🔐 DNS Configuration (Cloudflare Dashboard)

1. Go to: https://dash.cloudflare.com/
2. Select domain: `appsscale.com`
3. Go to: DNS > Records
4. Verify:
   ```
   Type: CNAME
   Name: ai
   Target: [your-tunnel-id].cfargotunnel.com
   Proxy: DNS only (orange cloud OFF)
   ```

---

## 📊 Architecture Diagram

```
User Browser
    ↓
https://ai.appsscale.com/automationtest/
    ↓
Cloudflare Tunnel (Windows)
    ↓
http://192.168.47.119:8080 (WSL)
    ↓
Chat Server
    ├─→ LM Studio API (Windows)
    └─→ Automation API (WSL:5000)
            ↓
    carrier.relayondemand.com
```

---

## 🔄 Complete Startup Procedure

### Step 1: Start WSL Services

```bash
cd /OnRelay/skills/carrier-browser-automation
./start_chat.sh
```

### Step 2: Restart Cloudflare Tunnel

On Windows:
```cmd
C:\Users\appsf\Desktop\OnRelay\restart_cf_tunnel.bat
```

### Step 3: Verify Access

Open browser:
```
https://ai.appsscale.com/automationtest/
```

You should see the chat interface with green status indicators.

---

## ✅ Success Checklist

- [ ] WSL services running (ports 5000, 8080)
- [ ] Cloudflare tunnel restarted
- [ ] Can access http://192.168.47.119:8080 from Windows
- [ ] Can access https://ai.appsscale.com/automationtest/
- [ ] Status indicators are green
- [ ] Can analyze forms
- [ ] LM Studio connected

---

## 📞 Quick Commands

### Restart Everything

```bash
# WSL - Restart services
cd /OnRelay/skills/carrier-browser-automation
./start_chat.sh
```

```cmd
REM Windows - Restart tunnel
C:\Users\appsf\Desktop\OnRelay\restart_cf_tunnel.bat
```

### Check Logs

```bash
# WSL logs
tail -f /tmp/chat_server.log
tail -f /tmp/automation_api.log
```

### Stop Services

```bash
# WSL
kill $(cat /tmp/automation_api.pid) $(cat /tmp/chat_server.pid)
```

```cmd
REM Windows
taskkill /F /IM cloudflared.exe
```

---

## 🎯 Next Steps

1. Test the chat interface at https://ai.appsscale.com/automationtest/
2. Try example commands:
   - "Analyze the current page"
   - "Fill form with sample data"
   - "Take a screenshot"
3. Verify all features work through the tunnel
4. Share URL with users for testing

---

## 📁 Related Files

| File | Location |
|------|----------|
| Cloudflare Config | `C:\Users\appsf\.cloudflared\config.yml` |
| Restart Script | `C:\Users\appsf\Desktop\OnRelay\restart_cf_tunnel.bat` |
| Chat Server | `/OnRelay/skills/carrier-browser-automation/chat_server.py` |
| Automation API | `/OnRelay/skills/carrier-browser-automation/api_server.py` |
