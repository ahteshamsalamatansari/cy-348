# Carrier Browser Automation Tool

## Overview
This tool provides a simple, robust browser automation solution for carrier.relayondemand.com with these key features:
- **Login**: Securely authenticates using credentials (apitest@test.com / test123)
- **Form Analysis**: Extracts all user input fields on authenticated pages
- **Fill & Submit**: Automates form filling based on LLM instructions
- **Session Persistence**: Maintains cookie session for multi-step workflows
- **Error Handling**: Gracefully handles CAPTCHAs, network issues, and failed logins without manual intervention
- **API Server**: REST API for integration with LM Studio and other LLMs

---

## Quick Start (LM Studio Integration)

### 1. Start the API Server

```bash
cd /OnRelay/skills/carrier-browser-automation
./start_server.sh
```

Or manually:
```bash
python3 api_server.py
```

The server starts on `http://localhost:5000`

### 2. Test the API

```bash
# Check server health
curl http://localhost:5000/health

# Analyze current page
curl http://localhost:5000/api/analyze
```

### 3. Use with LM Studio

See **[LM_STUDIO_GUIDE.md](LM_STUDIO_GUIDE.md)** for detailed instructions on integrating with LM Studio.

---

## Installation (for any model size)

1. Create skill directory:
   ```bash
   cd $CODEX_HOME/skills  # Default: ~/.codex/skills
   mkdir -p carrier-browser-automation
   ```
2. Copy these files into the directory:
   | File | Purpose |
   |------|---------|
   | `api_server.py` | REST API server for LLM integration |
   | `SKILL.md` | Core skill metadata (YAML frontmatter + workflow instructions) |
   | `README.md` | Setup guide, usage examples, and configuration notes |
   | `LM_STUDIO_GUIDE.md` | LM Studio integration guide |
3. Install dependencies:
   ```bash
   cd carrier-browser-automation
   pip install -r requirements.txt
   playwright install chromium
   ```
4. Set environment variables (optional, defaults are provided):
   ```bash
   echo "CARRIER_USERNAME=apitest@test.com" > ~/.carrier_env
   echo "CARRIER_PASSWORD=test123" >> ~/.carrier_env
   source ~/.carrier_env
   ```

---

## API Server Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Check if server is running |
| GET | `/api/analyze` | Analyze forms on current page |
| POST | `/api/fill` | Fill form with data |
| POST | `/api/navigate` | Navigate to a page |
| POST | `/api/click` | Click an element |
| GET | `/api/screenshot` | Take screenshot |
| POST | `/api/reset` | Reset session |

### Example API Calls

**Analyze Page:**
```bash
curl http://localhost:5000/api/analyze
```

**Fill Form:**
```bash
curl -X POST http://localhost:5000/api/fill \
  -H "Content-Type: application/json" \
  -d '{
    "form_id": "place-order-frm",
    "data": {
      "startAddress": "123 Main St"
    }
  }'
```

**Navigate:**
```bash
curl -X POST http://localhost:5000/api/navigate \
  -H "Content-Type: application/json" \
  -d '{"path": "/dispatch/create"}'
```

---

## CLI Usage (Recommended for Agents)

The easiest way to use this tool is via the command line interface.

### 1. Analyze Page
Logs in (if needed) and returns a JSON structure of all forms on the current page.
```bash
python3 scripts/automation.py analyze
```
**Output:**
```json
{
  "success": true,
  "login_status": "Logged in successfully",
  "current_url": "https://carrier.relayondemand.com/Carrier/dashboard",
  "forms": [...]
}
```

### 2. Submit Form
Fills and submits a form using a JSON data string.
```bash
python3 scripts/automation.py submit --data '{"email": "test@example.com", "password": "123"}'
```

### 3. Debug Page
Dumps the current page HTML (useful if analysis returns no forms).
```bash
python3 scripts/automation.py dump_html
```

### 4. Navigate
Navigate to a specific path and analyze the page.
```bash
python3 scripts/automation.py navigate /dispatch/create
```

### 5. Screenshot
Take a screenshot for debugging.
```bash
python3 scripts/automation.py screenshot /tmp/screenshot.png
```

---

## Core Functionality (Python API)

### Basic Usage Pattern:
```python
def run_task():
    """
    1. Verify session is valid
    2. Run analysis on current page
    3. Process LLM instructions to fill forms
    4. Return structured JSON response
    """
    from scripts.automation import CarrierAutomation

    # Step 1: Initialize tool and verify login
    automation = CarrierAutomation()
    session_result = automation.run_workflow()  # Returns success status + form data

    if not session_result['success']:
        return {"error": "Failed to log in, cannot process forms"}

    # Step 2: Get all user input fields on current page
    form_data = automation.analyze_forms()  # Returns JSON array of field objects

    # Step 3: Return data to LLM for processing (no need to understand this structure)
    return {"success": True, "form_structure": form_data}
```

### Example Model Instructions & Expected Output:
| Model Instruction | Tool Response |
|-------------------|---------------|
|"Analyze all user input fields on the current page"|JSON array with field names, types, and constraints (see below) |
|"Fill out form ID 'shipmentForm' with email='test@example.com', quantity=5"|Automates form submission with given values ✓ |

---

## Key Script Functions

`scripts/automation.py` contains:
- `run_workflow()`: Full sequence: login → analyze → return session state (simple JSON response)
- `analyze_forms()`: Returns structured JSON of all input fields with properties like "required", "placeholder", and validation rules
  ```json
  [{
    "form_id": "shipmentForm",
    "fields": [
      {"name":"email","type":"email","required":true,"placeholder":"Enter email address"},
      {"name":"quantity","type":"number","min":1,"max":100}
    ]
  }]
  ```

---

## Security Safeguards (No Code Changes Needed)
- Credentials are always loaded from environment variables, never hardcoded ✓
- All user input data is handled locally; nothing is sent over the network ✓
- Timeout of 30 seconds per request prevents hanging processes ✓

---

## Testing & Validation (For Model Developers)

Run unit tests to verify login workflow:
```bash
python3 -m unittest tests/unit_test_login.py
```

Run integration tests:
```bash
python3 -m pytest tests/integration_test.py
```

All tests are designed to be simple and fail gracefully if the site structure changes.

---

## Form Fields Found on Client Home Page

The tool discovered these fields on `/Carrier/client/home`:

| Field Name | Type | Placeholder | Description |
|------------|------|-------------|-------------|
| select | dropdown | - | Multiple dropdown fields |
| statrtAddress | text | "Enter Start Address" | Start address (note: typo in original) |
| BOL number... | text | "BOL number, pickup number..." | Public notes |
| For example... | text | "For example, tracking number..." | Internal notes (not shared with drivers) |

---

## Troubleshooting

### Server won't start
- Check if port 5000 is in use: `lsof -i :5000`
- Kill existing: `fuser -k 5000/tcp`

### Login fails
- Default credentials: apitest@test.com / test123
- Check internet connectivity

### Forms not detected
- Take screenshot to debug: `python3 scripts/automation.py screenshot /tmp/debug.png`
- Ensure you're on the correct page

### Browser errors
- Reinstall Playwright browsers: `playwright install chromium`
- Check WSL has internet access

---

## File Locations

| File | Location |
|------|----------|
| API Server | `/OnRelay/skills/carrier-browser-automation/api_server.py` |
| Automation Script | `/OnRelay/skills/carrier-browser-automation/scripts/automation.py` |
| Startup Script | `/OnRelay/skills/carrier-browser-automation/start_server.sh` |
| LM Studio Guide | `/OnRelay/skills/carrier-browser-automation/LM_STUDIO_GUIDE.md` |
| Storage | `~/.carrier_automation_storage/` |
| Logs | `/tmp/api_server.log` |

---

## Designed for 30-50B Models

This tool is specifically designed to be simple enough for smaller LLMs (30-50B parameters) to understand and use effectively:

- **Simple JSON responses** - No complex nested structures
- **Clear error messages** - Easy to understand what went wrong
- **Minimal dependencies** - Only requires Playwright and Flask
- **RESTful API** - Standard HTTP methods that any LLM can use
- **Comprehensive guides** - Step-by-step instructions for model and user
