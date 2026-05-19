#!/usr/bin/env python3
"""
Carrier Automation Chat Server

Serves the chat interface and proxies requests to LM Studio and Automation API.
This is needed because the Automation API runs on localhost:5000.

Run with: python3 chat_server.py
Then access at: http://localhost:9800 (or via Cloudflare tunnel)
"""

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
import requests
import os
import json

import re



import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(os.path.dirname(BASE_DIR), "web_interface")

app = Flask(__name__, static_folder=WEB_DIR)
CORS(app)  # Enable CORS for all routes

# Configuration - Direct to LM Studio API
# LM_STUDIO_BASE = os.environ.get("LM_STUDIO_API_BASE", "http://localhost:1234")
# LM_STUDIO_BASE = os.environ.get("LM_STUDIO_API_BASE", "http://192.168.10.13:1234")
LM_STUDIO_BASE = os.environ.get("LM_STUDIO_API_BASE", "http://127.0.0.1:1234")
LM_STUDIO_API = os.environ.get("LM_STUDIO_API", f"{LM_STUDIO_BASE}/v1/chat/completions")
AUTOMATION_API = "http://localhost:9500"
_FALLBACK_MODEL = os.environ.get("LM_STUDIO_MODEL", "nemotron-cascade-2-30b-a3b")

import time as _time
_cached_model = {"name": None, "ts": 0}

def get_active_model():
    """Get the currently loaded chat model from LM Studio (cached 60s).
    Queries api/v0/models for state=loaded, excludes embedding models.
    Falls back to env var LM_STUDIO_MODEL if LM Studio is unreachable."""
    now = _time.time()
    if _cached_model["name"] and now - _cached_model["ts"] < 60:
        return _cached_model["name"]
    try:
        resp = requests.get(f"{LM_STUDIO_BASE}/api/v0/models", timeout=3)
        if resp.ok:
            models = resp.json().get("data", [])
            chat = [m["id"] for m in models
                    if m.get("state") == "loaded" and "embed" not in m["id"].lower()]
            if chat:
                _cached_model["name"] = chat[0]
                _cached_model["ts"] = now
                return chat[0]
    except Exception:
        pass
    return _cached_model["name"] or _FALLBACK_MODEL


def strip_thinking(text):
    """Strip <think>...</think> blocks and 'Thinking Process:...' preambles from model output."""
    # Remove <think>...</think> tags (including unclosed <think> at end of truncated responses)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    text = re.sub(r'<think>.*$', '', text, flags=re.DOTALL).strip()
    # Remove "Thinking Process:..." preamble - try anchored version first, then greedy fallback
    text = re.sub(r'^Thinking Process:.*?(?=\n\n[A-Z{"\[])', '', text, flags=re.DOTALL).strip()
    # If entire text is still "Thinking Process:..." with no actual content, strip it all
    if text.startswith('Thinking Process:'):
        text = ''
    return text

@app.route('/')
def index():
    """Serve the chat interface"""
    return send_from_directory(WEB_DIR, 'automation_chat.html')

@app.route('/automationtest')
def automationtest_redirect():
    """Redirect /automationtest to /automationtest/"""
    from flask import redirect
    return redirect('/automationtest/')

@app.route('/automationtest/')
def automationtest():
    """Serve the chat interface at /automationtest/ path"""
    response = send_from_directory(WEB_DIR, 'automation_chat.html')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/automation_chat.html')
def chat_page():
    """Serve the chat interface at alternative path"""
    return send_from_directory(WEB_DIR, 'automation_chat.html')

@app.route('/automationtest/docs')
def automation_docs():
    """Serve the Carrier Dispatch AI documentation page"""
    response = send_from_directory(WEB_DIR, 'docs.html')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/filter-docs')
def filter_docs_page():
    """Serve the Smart Filter documentation page"""
    response = send_from_directory(WEB_DIR, 'filter-docs.html')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/api/proxy')
def proxy():
    """
    Proxy requests to the Automation API to avoid CORS issues.

    Query params:
    - url: The full URL to proxy to
    - method: HTTP method (default: GET)
    """
    target_url = request.args.get('url')
    method = request.args.get('method', 'GET')

    if not target_url:
        return jsonify({"error": "Missing 'url' parameter"}), 400

    # Restrict proxy to localhost only (prevent SSRF)
    from urllib.parse import urlparse
    parsed = urlparse(target_url)
    if parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
        return jsonify({"error": "Proxy restricted to localhost targets only"}), 403

    try:
        # Make the request to the Automation API
        if method == 'GET':
            resp = requests.get(target_url, timeout=60)
        elif method == 'POST':
            # Get JSON body from request
            data = request.get_json() if request.is_json else {}
            headers = {'Content-Type': 'application/json'}
            resp = requests.post(target_url, json=data, headers=headers, timeout=60)
        else:
            return jsonify({"error": f"Unsupported method: {method}"}), 400

        # Return the response
        return jsonify(resp.json()), resp.status_code

    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timed out"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze', methods=['GET'])
def analyze():
    """Proxy to automation API analyze endpoint"""
    try:
        resp = requests.get(f"{AUTOMATION_API}/api/analyze", timeout=180)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/fill', methods=['POST'])
def fill():
    """Proxy to automation API fill endpoint"""
    try:
        data = request.get_json()
        resp = requests.post(f"{AUTOMATION_API}/api/fill", json=data, timeout=180)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/navigate', methods=['POST'])
def navigate():
    """Proxy to automation API navigate endpoint"""
    try:
        data = request.get_json()
        resp = requests.post(f"{AUTOMATION_API}/api/navigate", json=data, timeout=180)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/click', methods=['POST'])
def click():
    """Proxy to automation API click endpoint"""
    try:
        data = request.get_json()
        resp = requests.post(f"{AUTOMATION_API}/api/click", json=data, timeout=180)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/screenshot', methods=['GET'])
def screenshot():
    """Proxy to automation API screenshot endpoint"""
    try:
        resp = requests.get(f"{AUTOMATION_API}/api/screenshot", timeout=180)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/submit', methods=['POST'])
def submit():
    """Proxy to automation API submit endpoint"""
    try:
        data = request.get_json()
        resp = requests.post(f"{AUTOMATION_API}/api/submit", json=data, timeout=180)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/expand_optional', methods=['POST'])
def expand_optional():
    """Proxy to automation API expand_optional endpoint"""
    try:
        data = request.get_json()
        resp = requests.post(f"{AUTOMATION_API}/api/expand_optional", json=data, timeout=180)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_dropdown_options', methods=['POST'])
def get_dropdown_options():
    """Proxy to automation API get_dropdown_options endpoint"""
    try:
        data = request.get_json()
        resp = requests.post(f"{AUTOMATION_API}/api/get_dropdown_options", json=data, timeout=180)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============== DIRECT API v2 PROXY ENDPOINTS ==============

@app.route('/api/v2/login', methods=['POST'])
def v2_login():
    """Proxy to automation API v2 login"""
    try:
        data = request.get_json() or {}
        resp = requests.post(f"{AUTOMATION_API}/api/v2/login", json=data, timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/context', methods=['GET'])
def v2_context():
    """Proxy to automation API v2 context"""
    try:
        resp = requests.get(f"{AUTOMATION_API}/api/v2/context", timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/form-types', methods=['GET'])
def v2_form_types():
    """Proxy to automation API v2 form types"""
    try:
        resp = requests.get(f"{AUTOMATION_API}/api/v2/form-types", timeout=15)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/reference-data', methods=['GET'])
def v2_reference_data():
    """Proxy to automation API v2 reference data"""
    try:
        resp = requests.get(f"{AUTOMATION_API}/api/v2/reference-data", timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/estimate', methods=['POST'])
def v2_estimate():
    """Proxy to automation API v2 estimate"""
    try:
        data = request.get_json()
        resp = requests.post(f"{AUTOMATION_API}/api/v2/estimate", json=data, timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/place-order', methods=['POST'])
def v2_place_order():
    """Proxy to automation API v2 place order"""
    try:
        data = request.get_json()
        resp = requests.post(f"{AUTOMATION_API}/api/v2/place-order", json=data, timeout=60)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/orders', methods=['GET'])
def v2_orders():
    """Proxy to automation API v2 orders"""
    try:
        resp = requests.get(f"{AUTOMATION_API}/api/v2/orders", params=request.args, timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/orders/<int:order_id>', methods=['GET'])
def v2_order_detail(order_id):
    """Proxy to automation API v2 order detail"""
    try:
        resp = requests.get(f"{AUTOMATION_API}/api/v2/orders/{order_id}", timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/orders/<int:order_id>/cancel', methods=['POST'])
def v2_cancel_order(order_id):
    """Proxy to automation API v2 cancel order"""
    try:
        data = request.get_json() or {}
        resp = requests.post(f"{AUTOMATION_API}/api/v2/orders/{order_id}/cancel", json=data, timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/drivers', methods=['GET'])
def v2_drivers():
    """Proxy to automation API v2 drivers"""
    try:
        resp = requests.get(f"{AUTOMATION_API}/api/v2/drivers", params=request.args, timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/quick-orders', methods=['GET'])
def v2_quick_orders():
    """Proxy to automation API v2 quick orders"""
    try:
        resp = requests.get(f"{AUTOMATION_API}/api/v2/quick-orders", timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/multi-driver-blocks', methods=['GET'])
def v2_multi_driver_blocks():
    """Proxy to automation API v2 multi driver blocks"""
    try:
        resp = requests.get(f"{AUTOMATION_API}/api/v2/multi-driver-blocks", timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v2/dashboard', methods=['GET'])
def v2_dashboard():
    """Proxy to automation API v2 dashboard"""
    try:
        resp = requests.get(f"{AUTOMATION_API}/api/v2/dashboard", timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check - verifies LM Studio and Automation API are reachable"""
    model = get_active_model()
    lm_ok = False
    try:
        resp = requests.get(f"{LM_STUDIO_BASE}/api/v0/models", timeout=3)
        lm_ok = resp.ok
    except Exception:
        pass
    api_ok = False
    try:
        resp = requests.get(f"{AUTOMATION_API}/health", timeout=3)
        api_ok = resp.ok
    except Exception:
        pass
    status = "healthy" if (lm_ok and api_ok) else "degraded"
    return jsonify({
        "status": status,
        "service": "Carrier Automation Chat Server",
        "model": model,
        "lm_studio": "ok" if lm_ok else "unreachable",
        "automation_api": "ok" if api_ok else "unreachable",
    })






@app.route('/api/predict', methods=['POST'])
def api_predict():
    try:
        data = request.get_json()

        resp = requests.post(
            "http://localhost:9900/predict",  # 👈 call your model server
            json=data,
            timeout=10
        )

        return jsonify(resp.json()), resp.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/automation/chat', methods=['POST'])
def chat():
    """
    Proxied LLM chat endpoint - adds model name server-side to hide it from clients.
    Supports streaming when stream=true is in the request body.
    """
    try:
        data = request.get_json()
        if not data or 'messages' not in data:
            return jsonify({"error": "Missing 'messages' in request body"}), 400

        stream = data.get('stream', False)

        payload = {
            "model": get_active_model(),
            "messages": data.get('messages', []),
            "temperature": data.get('temperature', 0.3),
            "max_tokens": data.get('max_tokens', 16000),
            "stream": stream
        }

        if stream:
            # Stream the response using SSE
            def generate():
                try:
                    resp = requests.post(LM_STUDIO_API, json=payload, timeout=180, stream=True)
                    for line in resp.iter_lines():
                        if line:
                            yield line.decode('utf-8') + '\n\n'
                except Exception as e:
                    yield f'data: {json.dumps({"error": str(e)})}\n\n'
            return Response(generate(), mimetype='text/event-stream',
                          headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
        else:
            resp = requests.post(LM_STUDIO_API, json=payload, timeout=180)
            result = resp.json()
            # Strip thinking content from non-streaming response
            if result.get('choices'):
                content = result['choices'][0].get('message', {}).get('content', '')
                result['choices'][0]['message']['content'] = strip_thinking(content)
            return jsonify(result), resp.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/automation/chat/vl', methods=['POST'])
def chat_vl():
    """
    Vision-Language chat endpoint - takes a screenshot of the current browser
    and sends it alongside the user message to the VL model.
    Falls back to DOM form data if screenshot is blank/unavailable.

    Request body:
    {
        "messages": [{"role": "user", "content": "What forms do you see?"}],
        "max_tokens": 1000
    }
    """
    import base64
    import subprocess
    import datetime

    try:
        data = request.get_json()
        if not data or 'messages' not in data:
            return jsonify({"error": "Missing 'messages' in request body"}), 400

        script_dir = os.path.join(BASE_DIR, 'scripts')
        script_path = os.path.join(script_dir, 'automation.py')

        # Only attempt screenshot if a vision-capable model is loaded
        model = get_active_model()
        is_vision_model = any(tag in model.lower() for tag in ('vl', 'vision', 'llava', 'cogvlm'))
        img_base64 = ""

        if is_vision_model:
            screenshot_path = f"/tmp/vl_screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            try:
                subprocess.run(
                    ['python3', script_path, '--quiet', 'screenshot', screenshot_path],
                    capture_output=True, text=True, timeout=90, cwd=script_dir
                )
                if os.path.exists(screenshot_path):
                    file_size = os.path.getsize(screenshot_path)
                    if file_size > 15000:
                        with open(screenshot_path, 'rb') as f:
                            img_base64 = base64.b64encode(f.read()).decode('utf-8')
                    os.remove(screenshot_path)
            except Exception:
                pass
        else:
            print(f"[VL] Skipping screenshot — model '{model}' is not vision-capable, using DOM text only")

        # Also fetch DOM form data as context (always useful)
        dom_context = ""
        try:
            dom_resp = requests.get(f"{AUTOMATION_API}/api/analyze", timeout=120)
            if dom_resp.ok:
                dom_data = dom_resp.json()
                dom_context = json.dumps(dom_data, indent=2)
        except Exception:
            pass

        # Build messages
        messages = data.get('messages', [])
        vl_messages = []

        for msg in messages:
            if msg.get('role') == 'user':
                # Add DOM context to user message text
                user_text = msg.get('content', '')
                if dom_context:
                    user_text += f"\n\n[PAGE DOM DATA]:\n{dom_context}"

                if img_base64:
                    # VL mode: send screenshot + text
                    vl_messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                        ]
                    })
                else:
                    # Text-only mode: send DOM data as context
                    vl_messages.append({
                        "role": "user",
                        "content": user_text
                    })
            else:
                vl_messages.append(msg)

        payload = {
            "model": get_active_model(),
            "messages": vl_messages,
            "temperature": data.get('temperature', 0.3),
            "max_tokens": data.get('max_tokens', 16000)
        }

        resp = requests.post(LM_STUDIO_API, json=payload, timeout=180)
        result = resp.json()

        # Strip thinking content from response
        if result.get('choices'):
            content = result['choices'][0].get('message', {}).get('content', '')
            result['choices'][0]['message']['content'] = strip_thinking(content)

        return jsonify(result), resp.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============== FILTER API ENDPOINTS ==============

@app.route('/filter.html')
def filter_page():
    """Serve the Smart Filter interface"""
    response = send_from_directory(WEB_DIR, 'filter.html')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# ---------------------------------------------------------------------------
# Server-side per-user message history for filter context
# Tracks the last FILTER_HISTORY_SIZE messages per user_id so the caller
# only needs to send user_id + message (no client-side history management).
# ---------------------------------------------------------------------------
import threading
_filter_lock = threading.Lock()

FILTER_HISTORY_SIZE = 5
FILTER_HISTORY_TTL = 1800  # 30 minutes — auto-expire stale sessions
_FILTER_HISTORY_HARD_CAP = 10000  # reject if total entries exceed this
_filter_history = {}  # {user_id: {"messages": [...], "last_seen": timestamp}}


def _get_user_history(user_id: str) -> list:
    """Get the last N messages for a user, pruning expired sessions."""
    with _filter_lock:
        now = _time.time()
        # Prune expired sessions
        expired = [k for k, v in _filter_history.items()
                   if now - v["last_seen"] > FILTER_HISTORY_TTL]
        for k in expired:
            del _filter_history[k]

        entry = _filter_history.get(user_id)
        if entry:
            return entry["messages"][-FILTER_HISTORY_SIZE:]
        return []


def _append_user_message(user_id: str, message: str) -> None:
    """Append a message to a user's history."""
    with _filter_lock:
        now = _time.time()
        # Prune expired sessions first
        expired = [k for k, v in _filter_history.items()
                   if now - v["last_seen"] > FILTER_HISTORY_TTL]
        for k in expired:
            del _filter_history[k]

        # Hard cap: reject if too many tracked users
        if user_id not in _filter_history and len(_filter_history) >= _FILTER_HISTORY_HARD_CAP:
            return  # silently drop — prevent unbounded growth

        if user_id not in _filter_history:
            _filter_history[user_id] = {"messages": [], "last_seen": 0}
        _filter_history[user_id]["messages"].append(message)
        _filter_history[user_id]["last_seen"] = now
        # Keep only recent messages
        if len(_filter_history[user_id]["messages"]) > FILTER_HISTORY_SIZE * 2:
            _filter_history[user_id]["messages"] = \
                _filter_history[user_id]["messages"][-FILTER_HISTORY_SIZE:]


@app.route('/api/filter', methods=['POST'])
def filter_message():
    """
    Smart Filter API - Detect contact information or circumvention attempts.
    Uses the local DistilBERT model server (runs.py) instead of LM Studio.
    """
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "Missing 'message' field in request body"}), 400

        message = data['message']
        if not isinstance(message, str) or not message.strip():
            return jsonify({"error": "message must be a non-empty string"}), 400
        message = message.strip()

        raw_uid = data.get('user_id') or data.get('username')
        user_id = (str(raw_uid).strip() if raw_uid else '') or 'anonymous'

        # Proxy to local model server (runs.py) on port 9900
        # runs.py handles history automatically if we pass user_id
        try:
            resp = requests.post(
                "http://localhost:9900/predict",
                json={"text": message, "user_id": user_id},
                timeout=15
            )
            
            if not resp.ok:
                return jsonify({
                    "safe": False,
                    "category": "ERROR",
                    "reason": f"Local model server returned {resp.status_code}"
                }), 502

            local_res = resp.json()
            prediction = local_res.get("prediction", "")
            
            # Map local model categories to filter API categories
            safe = True
            category = "CLEAN"
            reason = "No contact information detected"
            
            if "contact" in prediction:
                safe = False
                category = "PHONE"
                reason = "Contact information detected by local filter"
            elif prediction == "uncertain":
                safe = False
                category = "CIRCUMVENTION"
                reason = "Message flagged as suspicious or unclear"
            
            return jsonify({
                "safe": safe,
                "category": category,
                "reason": reason,
                "user_id": user_id,
                "context_size": len(local_res.get("history", [])),
                "confidence": local_res.get("confidence", 0)
            })

        except requests.exceptions.RequestException as e:
            return jsonify({
                "safe": False,
                "category": "ERROR",
                "reason": f"Failed to connect to local model server: {str(e)}"
            }), 503

    except Exception as e:
        return jsonify({
            "safe": False,
            "category": "ERROR",
            "reason": f"Internal filter error: {str(e)}"
        }), 500

@app.route('/api/filter/clear', methods=['POST'])
def filter_clear():
    """Clear server-side message history for a user."""
    data = request.get_json() or {}
    raw_uid = data.get('user_id') or data.get('username')
    user_id = (str(raw_uid).strip() if raw_uid else '') or 'anonymous'
    with _filter_lock:
        _filter_history.pop(user_id, None)
    return jsonify({"cleared": True, "user_id": user_id})

@app.route('/api/filter/health', methods=['GET'])
def filter_health():
    """Quick health check for the filter API (checks local model server)"""
    try:
        # Check the local model server (runs.py) on port 9900
        resp = requests.get("http://localhost:9900/", timeout=5)
        if resp.ok:
            return jsonify({
                "status": "ok", 
                "model": "Local DistilBERT Filter",
                "engine": "local"
            })
        return jsonify({
            "status": "degraded", 
            "reason": "Local model server (runs.py) not responding on port 9900"
        }), 503
    except Exception as e:
        return jsonify({
            "status": "error", 
            "reason": f"Local model server unreachable: {str(e)}"
        }), 503

@app.route('/api/filter/docs', methods=['GET'])
def filter_docs():
    """Return API documentation for the filter endpoint"""
    return jsonify({
        "endpoint": "/api/filter",
        "method": "POST",
        "description": "Analyze a message for contact information or circumvention attempts",
        "request": {
            "content_type": "application/json",
            "body": {
                "message": "(required) The message text to analyze",
                "context": "(optional) Array of previous messages for context-aware detection"
            }
        },
        "response": {
            "safe": "boolean - true if message is clean, false if detected",
            "category": "CLEAN | PHONE | EMAIL | SOCIAL | CIRCUMVENTION",
            "reason": "Human-readable explanation"
        },
        "examples": {
            "simple": {
                "request": {"message": "The package weighs 5kg"},
                "response": {"safe": True, "category": "CLEAN", "reason": "No contact information detected"}
            },
            "with_context": {
                "request": {
                    "message": "and ends with 1234",
                    "context": ["I'd like to talk offline", "My number starts with 555"]
                },
                "response": {"safe": False, "category": "PHONE", "reason": "User split phone number across messages: 555...1234"}
            }
        },
        "curl_example": "curl -X POST https://ai.appsscale.com/api/filter -H 'Content-Type: application/json' -d '{\"message\": \"Call me at five oh five 867 5309\"}'"
    })




if __name__ == '__main__':
    print("=" * 70)
    print("  Carrier Automation Chat Server")
    print("=" * 70)
    print()
    print("  This server provides:")
    print("  - Web interface for the AI chat")
    print("  - CORS proxy to Automation API (localhost:5000)")
    print("  - Direct access to automation endpoints")
    print()
    print(f"  Chat Interface: http://localhost:9800")
    print(f"  Automation API: {AUTOMATION_API}")
    print(f"  LM Studio API: {LM_STUDIO_API}")
    print()
    print("  For Cloudflare Tunnel:")
    print("  1. Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")
    print("  2. Run: cloudflared tunnel --url http://localhost:9800")
    print("  3. Access via the provided https URL")
    print()
    print("=" * 70)
    print()

    # Run the server
    app.run(host='0.0.0.0', port=9800, debug=False)
