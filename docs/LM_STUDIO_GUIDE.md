# LM Studio Integration Guide

## Quick Setup for LM Studio + Carrier Automation

This guide shows how to use the Carrier Browser Automation tool with LM Studio (Qwen 3 53B or similar 30-50B models).

---

## Step 1: Start the API Server

Open WSL terminal and run:

```bash
cd /OnRelay/skills/carrier-browser-automation
python3 api_server.py
```

The server will start on `http://localhost:5000`

Keep this terminal window open.

---

## Step 2: Configure LM Studio

In LM Studio, set up your API endpoint:

1. Open LM Studio
2. Load your model (Qwen 3 53B or similar)
3. The API server runs at: `http://localhost:5000`

---

## Step 3: Use the API Endpoints

### Available Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Check if server is running |
| GET | `/api/analyze` | Analyze forms on current page |
| POST | `/api/fill` | Fill form with data |
| POST | `/api/navigate` | Navigate to a page |
| POST | `/api/click` | Click an element |
| GET | `/api/screenshot` | Take screenshot |
| POST | `/api/reset` | Reset session |

---

## Example API Calls

### 1. Analyze Current Page

```bash
curl http://localhost:5000/api/analyze
```

**Response:**
```json
{
  "success": true,
  "current_url": "https://carrier.relayondemand.com/Carrier/client/home",
  "forms": [
    {
      "form_id": "place-order-frm",
      "field_count": 6,
      "fields": [
        {
          "field_name": "statrtAddress",
          "type": "text",
          "placeholder": "Enter Start Address",
          "required": false
        },
        ...
      ]
    }
  ],
  "total_fields": 6
}
```

### 2. Fill a Form

```bash
curl -X POST http://localhost:5000/api/fill \
  -H "Content-Type: application/json" \
  -d '{
    "form_id": "place-order-frm",
    "data": {
      "startAddress": "123 Main Street",
      "field2": "value"
    }
  }'
```

### 3. Navigate to Page

```bash
curl -X POST http://localhost:5000/api/navigate \
  -H "Content-Type: application/json" \
  -d '{"path": "/dispatch/create"}'
```

### 4. Take Screenshot

```bash
curl http://localhost:5000/api/screenshot
```

---

## System Prompt for LM Studio

Use this prompt in LM Studio to enable the model to use the automation:

```
You are an AI assistant with access to a browser automation tool for carrier.relayondemand.com.

Available Tool Endpoints (all at http://localhost:5000):

1. GET /api/analyze - Analyze forms on the current page
   Returns: Form structure with all fields

2. POST /api/fill - Fill out a form
   Body: {"form_id": "form-id", "data": {"field_name": "value"}}
   Returns: Success status

3. POST /api/navigate - Navigate to a page
   Body: {"path": "/page/path"}
   Returns: New page forms

4. POST /api/click - Click an element
   Body: {"selector": "css-selector"}
   Returns: Page after click

5. GET /api/screenshot - Take screenshot
   Returns: Screenshot file path

Workflow:
1. When user asks to interact with carrier website, first call /api/analyze
2. Review the form structure returned
3. Ask user for field values if needed
4. Call /api/fill with the data
5. Confirm success to user

Always analyze forms before filling them to understand field names and types.
```

---

## Example Conversation

**User:** "I need to create a dispatch order on the carrier website"

**Assistant:** "Let me analyze the current page to see what forms are available."

[Model calls GET /api/analyze]

**Assistant:** "I can see a form with 6 fields on the current page:
- Field 1: Dropdown select
- Field 2: Start Address (text input)
- Field 3: Dropdown select
- Field 4: Dropdown select
- Field 5: BOL/pickup/delivery notes (text)
- Field 6: Internal notes (text)

What information would you like to fill in for this dispatch order?"

**User:** "Start address: 123 Main St, and internal note: test order"

**Assistant:** [Calls POST /api/fill with data]
"I've filled out the form with:
- Start Address: 123 Main St
- Internal Notes: test order

The form has been submitted successfully!"

---

## Form Field Names Found

Based on the analysis, here are the available field names:

| Field Name | Type | Description |
|------------|------|-------------|
| statrtAddress | text | Start address (note: typo in original) |
| select | dropdown | Multiple dropdown fields |
| BOL number... | text | Public notes |
| For example... | text | Internal notes (not shared with drivers) |

---

## Troubleshooting

### Server won't start
- Check if port 5000 is already in use: `netstat -tlnp | grep 5000`
- Kill existing process: `pkill -f api_server.py`

### Login fails
- The tool uses credentials: apitest@test.com / test123
- Check internet connectivity

### Forms not detected
- Try taking a screenshot: `curl http://localhost:5000/api/screenshot`
- Navigate to the correct page first

---

## File Locations

- **API Server:** `/OnRelay/skills/carrier-browser-automation/api_server.py`
- **Automation Script:** `/OnRelay/skills/carrier-browser-automation/scripts/automation.py`
- **Logs:** `/tmp/api_server.log`

---

## Security Notes

- Credentials are stored as environment variables
- The API server runs on localhost only
- No data is sent externally except to carrier.relayondemand.com
- Browser storage is persisted in `~/.carrier_automation_storage/`
