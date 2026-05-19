#!/usr/bin/env python3
"""
Carrier Automation API Server

Provides two sets of endpoints:
  /api/*     - Playwright browser automation (legacy, slower but can handle any page)
  /api/v2/*  - Direct HTTP API calls to Relay On Demand (fast, reliable)

PORT: 9500
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import subprocess
import json
import os
import sys


from train_model import train_model

# Add scripts dir to path so we can import relay_api
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
from relay_api import RelayAPI

app = Flask(__name__)
CORS(app)

# Root route for basic health check/info
@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "status": "online",
        "message": "Carrier Automation API is running",
        "endpoints": {
            "health": "/health",
            "analyze": "/api/analyze (GET/POST)",
            "fill": "/api/fill (POST)"
        }
    })

# Shared Relay API instance (session persists across requests)
_relay_api = RelayAPI()
_relay_api_lock = threading.Lock()

def run_automation_command(command_args):
    """
    Run automation script as subprocess to avoid Playwright sync issues.
    This is a simple approach that works reliably.
    """
    script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
    script_path = os.path.join(script_dir, 'automation.py')
    cmd = ['python3', script_path, '--quiet'] + command_args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            cwd=script_dir
        )

        # Try to parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid JSON response", "raw_output": result.stdout}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}




training_status = {"running": False}

@app.route('/api/train', methods=['POST'])
def train():
    global training_status

    if training_status["running"]:
        return jsonify({"success": False, "message": "Training already running"}), 400

    def run_training():
        global training_status
        training_status["running"] = True
        try:
            train_model()
        finally:
            training_status["running"] = False

    thread = threading.Thread(target=run_training)
    thread.start()

    return jsonify({
        "success": True,
        "message": "Training started in background"
    })

@app.route('/api/train/status', methods=['GET'])
def train_status():
    return jsonify({
        "running": training_status["running"]
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Check if the API server is running."""
    return jsonify({
        "status": "healthy",
        "service": "Carrier Browser Automation API",
        "version": "1.0.0"
    })

@app.route('/api/analyze', methods=['GET', 'POST'])
def analyze_page():
    """
    Analyze the current page and return all forms with their fields.

    Simple GET/POST endpoint that returns form data.

    Returns:
    {
        "success": true,
        "current_url": "https://...",
        "forms": [...],
        "total_fields": 6
    }
    """
    try:
        result = run_automation_command(['analyze'])
        status_code = 200 if result.get('success') else 500
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/fill', methods=['POST'])
def fill_form():
    """
    Fill out a form with the provided data.

    POST /api/fill
    Body: {
        "form_id": "place-order-frm",  (optional)
        "data": {
            "startAddress": "123 Main St",
            "field2": "value"
        }
    }

    Returns:
    {
        "success": true,
        "message": "Form submitted"
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        form_id = data.get('form_id', '')
        field_data = data.get('data', {})

        if not field_data:
            return jsonify({"success": False, "error": "No field data provided"}), 400

        # Get optional button to click after filling
        click_button = data.get('click_button', '')

        # Build command
        args = ['submit']
        if form_id:
            args.extend(['--form-id', form_id])
        args.extend(['--data', json.dumps(field_data)])
        if click_button:
            args.extend(['--click-button', click_button])

        result = run_automation_command(args)
        status_code = 200 if result.get('success') else 500
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/navigate', methods=['POST'])
def navigate():
    """
    Navigate to a specific path on the carrier website.

    POST /api/navigate
    Body: {
        "path": "/dispatch/create"
    }

    Returns:
    {
        "success": true,
        "current_url": "https://...",
        "forms": [...]
    }
    """
    try:
        data = request.json
        path = data.get('path', '')

        if not path:
            return jsonify({"success": False, "error": "No path provided"}), 400

        result = run_automation_command(['navigate', path])
        status_code = 200 if result.get('success') else 500
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/click', methods=['POST'])
def click_element():
    """
    Click an element on the page using CSS selector.

    POST /api/click
    Body: {
        "selector": "button:has-text('Create')"
    }

    Returns:
    {
        "success": true,
        "forms": [...]
    }
    """
    try:
        data = request.json
        selector = data.get('selector', '')

        if not selector:
            return jsonify({"success": False, "error": "No selector provided"}), 400

        result = run_automation_command(['click', selector])
        status_code = 200 if result.get('success') else 500
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/screenshot', methods=['GET', 'POST'])
def screenshot():
    """
    Take a screenshot of the current page.

    GET /api/screenshot
    POST /api/screenshot
    Body (optional): {
        "path": "/tmp/screenshot.png"
    }

    Returns:
    {
        "success": true,
        "path": "/tmp/screenshot_123.png"
    }
    """
    try:
        import datetime
        default_path = f"/tmp/screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        if request.method == 'POST':
            data = request.json or {}
            path = data.get('path', default_path)
        else:
            path = default_path

        result = run_automation_command(['screenshot', path])
        status_code = 200 if result.get('success') else 500
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_session():
    """
    Reset the browser session.

    POST /api/reset

    Returns:
    {
        "success": true,
        "message": "Session reset"
    }
    """
    try:
        # Simply remove the storage file to reset
        storage_file = os.path.expanduser('~/.carrier_automation_storage/storage_state.json')
        if os.path.exists(storage_file):
            os.remove(storage_file)

        return jsonify({"success": True, "message": "Session reset successfully"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/submit', methods=['POST'])
def submit_form():
    """
    Click a submit button to submit the form.

    POST /api/submit
    Body: {
        "button": "Assign a Driver" or "Find me a Driver"
    }

    Returns:
    {
        "success": true,
        "message": "Button clicked"
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        button_text = data.get('button', 'Assign a Driver')

        # Build command to click the button
        args = ['click', f'button:has-text("{button_text}")']

        result = run_automation_command(args)
        return jsonify(result), 200 if result.get('success') else 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/expand_optional', methods=['POST'])
def expand_optional():
    """
    Click on an optional section to expand it.

    POST /api/expand_optional
    Body: {
        "section": "Trailer Type" or "Endorsements" or "Unit Numbers"
    }

    Returns the updated form analysis after expanding.
    """
    try:
        data = request.json
        section = data.get('section', '')

        # Map section names to label text
        section_map = {
            "Trailer Type": "Trailer Type Experience",
            "Endorsements": "Endorsements",
            "Unit Numbers": "Unit Numbers"
        }

        search_text = section_map.get(section, section)

        # Click the optional div containing this text
        args = ['click', f'.optional-div:has-text("{search_text}")']

        result = run_automation_command(args)
        return jsonify(result), 200 if result.get('success') else 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/get_dropdown_options', methods=['POST'])
def get_dropdown_options():
    """
    Get options for a specific dropdown by clicking it.

    POST /api/get_dropdown_options
    Body: {
        "field": "WhenYouWantDriver" or "DriverBookDurations" or "DriverPayType"
    }
    """
    try:
        data = request.json
        field = data.get('field', '')

        # This will click the dropdown to reveal options and return them
        args = ['get_options', field]

        result = run_automation_command(args)
        return jsonify(result), 200 if result.get('success') else 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ============== DIRECT API ENDPOINTS (v2) ==============
# These call the Relay REST API directly - no browser needed.

import time as _time
_auth_timestamp = 0
_AUTH_TTL = 3600  # Re-authenticate every hour

def _ensure_relay_auth():
    """Ensure the Relay API client is authenticated (re-auth after TTL or on failure)."""
    global _auth_timestamp
    with _relay_api_lock:
        now = _time.time()
        if _relay_api.is_authenticated and (now - _auth_timestamp) > _AUTH_TTL:
            _relay_api.auth_token = None  # Force re-login after TTL
        if not _relay_api.is_authenticated:
            result = _relay_api.login()
            if not result["success"]:
                return False, result
            _auth_timestamp = now
        return True, None

@app.route('/api/v2/login', methods=['POST'])
def v2_login():
    """
    Authenticate with the Relay API.
    POST /api/v2/login
    Body (optional): { "email": "...", "password": "..." }
    """
    try:
        data = request.json or {}
        with _relay_api_lock:
            result = _relay_api.login(
                email=data.get('email'),
                password=data.get('password'),
            )
        return jsonify(result), 200 if result.get('success') else 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v2/context', methods=['GET'])
def v2_context():
    """
    Get complete context for the LLM: form types, reference data, carrier info.
    This replaces the Playwright-based page analysis with direct API data.

    GET /api/v2/context

    Returns: { form_types, reference_data, carrier }
    """
    try:
        ok, err = _ensure_relay_auth()
        if not ok:
            return jsonify(err), 401

        with _relay_api_lock:
            context = _relay_api.get_form_context()
        context["success"] = True
        return jsonify(context), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v2/form-types', methods=['GET'])
def v2_form_types():
    """Get descriptions of all available form types."""
    return jsonify({
        "success": True,
        "form_types": RelayAPI.get_form_types(),
    }), 200

@app.route('/api/v2/reference-data', methods=['GET'])
def v2_reference_data():
    """
    Get reference data (task types, trailer types, endorsements).
    GET /api/v2/reference-data
    """
    try:
        ok, err = _ensure_relay_auth()
        if not ok:
            return jsonify(err), 401

        with _relay_api_lock:
            data = {
                "success": True,
                "task_types": _relay_api.get_task_types(),
                "trailer_types": _relay_api.get_trailer_types(),
                "endorsement_types": _relay_api.get_endorsement_types(),
            }
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v2/estimate', methods=['POST'])
def v2_estimate():
    """
    Get estimated distance, cost, and time for an order.
    POST /api/v2/estimate
    Body: order data (same fields as place_order)
    """
    try:
        ok, err = _ensure_relay_auth()
        if not ok:
            return jsonify(err), 401

        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        with _relay_api_lock:
            result = _relay_api.get_estimated_distance(data)
        result["success"] = result.get("Status", False)
        if not result["success"]:
            raw_msg = result.get("Message", "")
            if "GetCarrierDriverDetailsById" in raw_msg or "Object reference not set" in raw_msg:
                result["user_error"] = (
                    "The Relay server could not calculate an estimate. "
                    "This may be due to the carrier account not being fully set up."
                )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v2/place-order', methods=['POST'])
def v2_place_order():
    """
    Submit a new order via direct API call.

    POST /api/v2/place-order
    Body: Complete order data or simplified fields that get built into order data.

    Simplified body example:
    {
        "start_address": "123 Main St, City, ST",
        "destination_address": "456 Oak Ave, City, ST",
        "when_want_driver": "2",
        "driver_pay_type": "0",
        "driver_book_duration": "2",
        "flat_amount": "150",
        "trailer_type_id": "2",
        "special_notes": "Call upon arrival",
        "form_type": "quick_entry"
    }

    Or raw order data (passed directly to PlaceOrder/NewOrder).
    """
    try:
        ok, err = _ensure_relay_auth()
        if not ok:
            return jsonify(err), 401

        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        with _relay_api_lock:
            # If it looks like simplified data (has start_address), build full payload
            if "start_address" in data or "StartAddress" not in data:
                form_type = data.pop("form_type", "quick_entry")

                order_data = _relay_api.build_order_data(
                    start_address=data.get("start_address", data.get("StartAddress", "")),
                    destination_address=data.get("destination_address", data.get("DestinationAddress", "")),
                    when_want_driver=str(data.get("when_want_driver", data.get("WhenYouWantDriver", "2"))),
                    driver_pay_type=str(data.get("driver_pay_type", data.get("DriverPayType", "0"))),
                    driver_book_duration=str(data.get("driver_book_duration", data.get("DriverBookDurations", "2"))),
                    flat_amount=str(data.get("flat_amount", data.get("FlatAmount", ""))),
                    hourly_amount=str(data.get("hourly_amount", data.get("HourlyFlatAmount", ""))),
                    per_load_amount=str(data.get("per_load_amount", data.get("PerLoadAmount", ""))),
                    per_mile_amount=str(data.get("per_mile_amount", data.get("PerMileAmount", ""))),
                    per_week_amount=str(data.get("per_week_amount", data.get("PerWeekAmount", ""))),
                    total_loads=str(data.get("total_loads", data.get("TotalLoads", ""))),
                    estimated_total_miles=str(data.get("estimated_total_miles", data.get("EstimatedTotalMiles", ""))),
                    trailer_type_id=str(data.get("trailer_type_id", data.get("TrailerTypeID", ""))),
                    truck_unit_number=str(data.get("truck_unit_number", data.get("TruckUnitNumber", ""))),
                    trailer_number=str(data.get("trailer_number", data.get("TrailerNumber", ""))),
                    special_notes=str(data.get("special_notes", data.get("SpecialNotes", ""))),
                    internal_notes=str(data.get("internal_notes", data.get("InternalNotes", ""))),
                    endorsement_types=data.get("endorsement_types", data.get("EndorsementTypes")),
                    additional_stops=data.get("additional_stops", data.get("AdditionalStops")),
                    schedule_time=str(data.get("schedule_time", data.get("ScheduleTime", ""))),
                    is_one_way=data.get("is_one_way", data.get("IsOneWay", True)),
                    from_smart_wizard=(form_type == "smart_wizard"),
                    order_assign=data.get("order_assign", data.get("OrderAssign", "Find")),
                    preferred_driver_id=str(data.get("preferred_driver_id", data.get("PreferredRelayDriverId", ""))),
                    carrier_driver_id=str(data.get("carrier_driver_id", data.get("CarrierDriverID", ""))),
                    carrier_driver_name=str(data.get("carrier_driver_name", data.get("CarrierDriverName", ""))),
                    schedule_date=str(data.get("schedule_date", data.get("ScheduleDate", ""))),
                    start_lat=str(data.get("start_lat", data.get("StartAddressLat", ""))),
                    start_lng=str(data.get("start_lng", data.get("StartAddressLong", ""))),
                    start_city=str(data.get("start_city", data.get("StartAddressCity", ""))),
                    start_state=str(data.get("start_state", data.get("StartAddressStateCode", ""))),
                    dest_lat=str(data.get("dest_lat", data.get("DestinationAddressLat", ""))),
                    dest_lng=str(data.get("dest_lng", data.get("DestinationAddressLong", ""))),
                    dest_city=str(data.get("dest_city", data.get("DestinationAddressCity", ""))),
                    dest_state=str(data.get("dest_state", data.get("DestinationAddressStateCode", ""))),
                    start_task_id=str(data.get("start_task_id", data.get("StartAddressTaskID", ""))),
                    start_task_hour=str(data.get("start_task_hour", data.get("StartAddressTaskHour", ""))),
                    end_task_id=str(data.get("end_task_id", data.get("EndAddressTaskID", ""))),
                    end_task_hour=str(data.get("end_task_hour", data.get("EndAddressTaskHour", ""))),
                )
            else:
                # Raw order data - pass directly
                order_data = data

            result = _relay_api.place_order(order_data)

        result["success"] = result.get("Status", False)

        # Translate common Relay API errors into user-friendly messages
        if not result["success"]:
            raw_msg = result.get("Message", "")
            if "Index was out of range" in raw_msg:
                result["user_error"] = (
                    "The order is missing scheduling information. "
                    "Please provide when you need the driver (e.g., exact date/time, "
                    "timeframe, or 'not sure')."
                )
            elif "Object reference not set" in raw_msg:
                result["user_error"] = (
                    "The Relay server encountered a data error. This can happen if "
                    "the carrier account is not fully set up (missing driver records, "
                    "inactive account, or incomplete profile). Please verify the "
                    "account is active and has at least one driver configured."
                )
            elif "GetCarrierDriverDetailsById" in raw_msg:
                result["user_error"] = (
                    "The carrier account does not have a valid driver profile. "
                    "Please ensure a driver is added to the account before placing orders."
                )

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v2/orders', methods=['GET'])
def v2_orders():
    """
    Get current orders.
    GET /api/v2/orders?type=now|scheduled|all
    """
    try:
        ok, err = _ensure_relay_auth()
        if not ok:
            return jsonify(err), 401

        order_type = request.args.get('type', 'now')
        with _relay_api_lock:
            if order_type == 'scheduled':
                result = _relay_api.get_scheduled_orders()
            elif order_type == 'all':
                result = _relay_api.get_orders()
            else:
                result = _relay_api.get_current_orders()

        # Relay API returns Status=false for empty results; treat as success if Message="Success"
        result["success"] = result.get("Status", True) or result.get("Message") == "Success"
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v2/orders/<int:order_id>', methods=['GET'])
def v2_order_detail(order_id):
    """Get detail for a specific order."""
    try:
        ok, err = _ensure_relay_auth()
        if not ok:
            return jsonify(err), 401

        with _relay_api_lock:
            result = _relay_api.get_order_detail(order_id)
        result["success"] = True
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v2/orders/<int:order_id>/cancel', methods=['POST'])
def v2_cancel_order(order_id):
    """Cancel an order."""
    try:
        ok, err = _ensure_relay_auth()
        if not ok:
            return jsonify(err), 401

        data = request.json or {}
        with _relay_api_lock:
            result = _relay_api.cancel_order(order_id, data.get('reason', ''))
        result["success"] = result.get("Status", False)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v2/drivers', methods=['GET'])
def v2_drivers():
    """
    Get carrier drivers.
    GET /api/v2/drivers?type=own|preferred|active
    """
    try:
        ok, err = _ensure_relay_auth()
        if not ok:
            return jsonify(err), 401

        driver_type = request.args.get('type', 'own')
        with _relay_api_lock:
            if driver_type == 'preferred':
                result = _relay_api.get_preferred_drivers()
            elif driver_type == 'active':
                result = _relay_api.get_active_drivers()
            else:
                result = _relay_api.get_carrier_drivers()

        result["success"] = result.get("Status", True)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v2/quick-orders', methods=['GET'])
def v2_quick_orders():
    """Get saved quick order templates."""
    try:
        ok, err = _ensure_relay_auth()
        if not ok:
            return jsonify(err), 401

        with _relay_api_lock:
            result = _relay_api.get_quick_orders()
        result["success"] = result.get("Status", True)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v2/multi-driver-blocks', methods=['GET'])
def v2_multi_driver_blocks():
    """Get multi driver blocks."""
    try:
        ok, err = _ensure_relay_auth()
        if not ok:
            return jsonify(err), 401

        with _relay_api_lock:
            result = _relay_api.get_multi_driver_blocks()
        result["success"] = result.get("Status", True)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v2/dashboard', methods=['GET'])
def v2_dashboard():
    """Get dashboard counts and carrier info."""
    try:
        ok, err = _ensure_relay_auth()
        if not ok:
            return jsonify(err), 401

        with _relay_api_lock:
            result = {
                "success": True,
                "counts": _relay_api.get_dashboard_counts(),
                "notifications": _relay_api.get_notification_count(),
            }
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "error": "Internal server error"}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("  Carrier Automation API Server")
    print("=" * 60)
    print()
    print("  Browser Automation (Playwright):")
    print("  - GET  /api/analyze          - Analyze page forms")
    print("  - POST /api/fill             - Fill form with data")
    print("  - POST /api/navigate         - Navigate to path")
    print("  - POST /api/click            - Click element")
    print("  - GET  /api/screenshot       - Take screenshot")
    print("  - POST /api/reset            - Reset browser session")
    print()
    print("  Direct API (v2 - faster, no browser):")
    print("  - POST /api/v2/login         - Authenticate")
    print("  - GET  /api/v2/context       - Full LLM context")
    print("  - GET  /api/v2/form-types    - Form type descriptions")
    print("  - GET  /api/v2/reference-data - Task/trailer/endorsement types")
    print("  - POST /api/v2/estimate      - Distance/cost estimate")
    print("  - POST /api/v2/place-order   - Submit order")
    print("  - GET  /api/v2/orders        - List orders")
    print("  - GET  /api/v2/drivers       - List drivers")
    print("  - GET  /api/v2/quick-orders  - Quick order templates")
    print("  - GET  /api/v2/multi-driver-blocks  - MDB list")
    print("  - GET  /api/v2/dashboard     - Dashboard counts")
    print()
    print("  Starting server on http://0.0.0.0:9500")
    print("=" * 60)
    print()

    # Run the server
    app.run(host='0.0.0.0', port=9500, debug=False, threaded=True)
