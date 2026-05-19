from flask import Flask, request, jsonify
import torch
import re
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification

from collections import defaultdict
from threading import Lock
from flask_cors import CORS

user_history = defaultdict(list)
lock = Lock()
MAX_HISTORY = 5

app = Flask(__name__)
CORS(app)

# -----------------------------
# CONFIG
# -----------------------------
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model")
DEVICE = torch.device("cpu")

# -----------------------------
# LOAD MODEL (ONLY ONCE)
# -----------------------------
print("Loading model...")
model = DistilBertForSequenceClassification.from_pretrained(MODEL_PATH)
tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_PATH)
tokenizer.truncation_side = 'left'

model.to(DEVICE)
model.eval()
torch.set_num_threads(2)
print("Model loaded ✅")

# -----------------------------
# REGEX LAYER
# -----------------------------
def regex_check(text):
    text_lower = text.lower()

    # -------------------------
    # 1. NORMAL PHONE
    # -------------------------
    phone = re.search(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", text)

    # -------------------------
    # 2. EMAIL
    # -------------------------
    email = re.search(r"\S+@\S+\.\S+", text)

    # -------------------------
    # 3. OBFUSCATED EMAIL
    # -------------------------
    normalized = re.sub(r"\s+", "", text_lower)

    obf_email = re.search(
        r"[a-z0-9._%+-]+(?:at|@)[a-z0-9.-]+(?:dot|\.)[a-z]{2,}",
        normalized
    )

    # -------------------------
    # 4. SPLIT PHONE 🔥
    # -------------------------
    # Remove numbers associated with common units (time, distance, weight, ordinals)
    # This prevents false positives on trucking/logistic terms.
    cleaned_text = re.sub(r'\b\d+(?:\.\d+)?\s*(am|pm|st|nd|rd|th|km|mi|mile|miles|lb|lbs|kg|g|oz|ft|in|cm|m|hr|hrs|hour|hours|min|mins|sec|secs)\b', '', text_lower)
    
    # Strip times (e.g. 12:30) and currency ($500)
    cleaned_text = re.sub(r'\b\d{1,2}:\d{2}(?:\s*(?:am|pm))?\b', '', cleaned_text)
    cleaned_text = re.sub(r'\$\d+(?:\.\d+)?', '', cleaned_text)
    
    digits = re.findall(r"\d+", cleaned_text)

    split_phone = False
    if digits:
        merged = "".join(digits)

        if len(merged) >= 7:
            if re.search(r"\d{7,}", merged):
                split_phone = True

    return bool(phone or email or obf_email or split_phone)


# -----------------------------
# PREDICT FUNCTION
# -----------------------------
def predict(text):
    if regex_check(text):
        return {"prediction": "contact (regex)", "confidence": 1.0}

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=128
    )

    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    probs = torch.softmax(outputs.logits, dim=1)
    label = torch.argmax(probs).item()
    confidence = probs[0][label].item()

    if confidence < 0.7:
        return {"prediction": "uncertain", "confidence": confidence}

    return {
        "prediction": "contact" if label == 1 else "no_contact",
        "confidence": confidence
    }

# -----------------------------
# API ROUTES
# -----------------------------

@app.route('/')
def home():
    return "Model API is running"

# @app.route('/predict', methods=['POST'])
# def api_predict():
#     data = request.get_json()

#     text = data.get("text", "")
#     user_id = data.get("user_id", "anonymous")

#     if not text:
#         return jsonify({"error": "text is required"}), 400

#     with lock:
#         user_history[user_id].append(text)

#         if len(user_history[user_id]) > MAX_HISTORY:
#             user_history[user_id] = user_history[user_id][-MAX_HISTORY:]

#         combined_text = " ".join(user_history[user_id])

#         # ✅ COPY history (important to avoid mutation issues)
#         history_copy = list(user_history[user_id])

#     result = predict(combined_text)

#     # ✅ RETURN HISTORY
#     return jsonify({
#         **result,
#         "history": history_copy,
#         "combined_text": combined_text
#     })


@app.route('/predict', methods=['POST'])
def api_predict():
    data = request.get_json()

    text = data.get("text", "")
    user_id = data.get("user_id", "anonymous")

    if not text:
        return jsonify({"error": "text is required"}), 400

    with lock:
        # 1. Create a temporary history to evaluate this message
        temp_history = user_history[user_id] + [text]
        if len(temp_history) > MAX_HISTORY:
            temp_history = temp_history[-MAX_HISTORY:]

        combined_text = " ".join(temp_history)

    # 3. Predict
    # Run strict regex on the combined history to catch split numbers
    if regex_check(combined_text):
        result = {"prediction": "contact (regex)", "confidence": 1.0}
    else:
        # Run ML model ONLY on the current message to prevent hallucinations from noisy history
        result = predict(text)

    # Determine if message is safe
    is_contact = result.get("prediction") in ["contact", "contact (regex)"]

    with lock:
        # 4. ONLY save the message to history if it is clean (safe)
        if not is_contact:
            user_history[user_id].append(text)
            if len(user_history[user_id]) > MAX_HISTORY:
                user_history[user_id] = user_history[user_id][-MAX_HISTORY:]
        
        history_copy = list(user_history[user_id])

    return jsonify({
        **result,
        "history": history_copy,
        "combined_text": combined_text,
        "reset": False
    })


@app.route('/clear_history', methods=['POST'])
def clear_history():
    data = request.get_json()
    user_id = data.get("user_id", "anonymous")

    with lock:
        old_history = list(user_history[user_id])  # save before clearing
        user_history[user_id] = []

    return jsonify({
        "status": "cleared",
        "old_history": old_history,
        "new_history": []
    })

# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=9900, debug=True)