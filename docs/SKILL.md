---
name: carrier-browser-automation
short-description: Browser automation for carrier.relayondemand.com with login flow and form analysis
metadata:
  short-description: Browser automation for carrier.relayondemand.com with login flow and form analysis
---

# Carrier Browser Automation Skill

## Overview

This skill provides a complete workflow for automating browser interactions on https://carrier.relayondemand.com/Carrier/login, including secure login with credentials (apitest@test.com / Bbcimlr!) and analyzing user input forms. The automation follows these core steps:
1. **Login sequence**: Navigate to login page, enter username/password, handle any security challenges, and verify successful access
2. **Form analysis**: Identify all user input fields on authenticated pages, capture their structure, data types, and validation rules
3. **Interaction framework**: Execute actions on these forms (populate, submit) while maintaining session state
4. **Error handling**: Detect login failures, form errors, network issues, and recover gracefully
5. **Session management**: Maintain persistent browser sessions for multi-step workflows

## Core Capabilities

### Login Workflow
- Navigate to https://carrier.relayondemand.com/Carrier/login
- Enter username: apitest@test.com
- Enter password: Bbcimlr!
- Handle CAPTCHAs, 2FA, or security questions if present (fallback to manual verification)
- Verify successful navigation to authenticated homepage
- Store session cookies/authentication tokens for subsequent requests

### Form Analysis Protocol
1. **DOM Parsing**: Extract all input elements (text, dropdowns, checkboxes, radio buttons, file uploads, etc.)
2. **Data Modeling**: Capture name attributes, placeholder text, validation rules, and default values
3. **Error Detection**: Identify required fields, error messages, and field constraints
4. **Interaction Mapping**: Create a structured JSON representation of each form for automated processing

### Browser Automation Engine
- Uses Playwright with headless Chrome/Chromium
- Maintains persistent browser context across actions
- Handles cookies, local storage, and session persistence
- Implements timeout mechanisms for slow network requests

## Usage Pattern (for other skills/tools)
1. **CLI Mode (Recommended)**:
   Execute the script directly from the shell:
   ```bash
   # Analyze forms
   python3 skills/carrier-browser-automation/scripts/automation.py analyze
   
   # Submit data
   python3 skills/carrier-browser-automation/scripts/automation.py submit --data '{"field": "value"}'
   ```

2. **Python Import Mode**:
   Import skill via `skill-installer` or copy directory to `$CODEX_HOME/skills`
   Call automation functions with:
   ```python
def run_workflow():
    """
    Execute full login and form analysis workflow on carrier.relayondemand.com
    Returns structured JSON of found forms and successful session state
    """
```

## Setup Requirements
- Node.js 18+ or Python 3.10+
- Playwright browsers (chromium) installed via `playwright install`
- Environment variables: CARRIER_USERNAME=apitest@test.com, CARRIER_PASSWORD=Bbcimlr!
