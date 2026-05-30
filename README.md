# Relay On Demand - Carrier Browser Automation & Smart Filter

This repository contains the Carrier Browser Automation system and the AI-based Smart Chat Filtration system for Relay On Demand. The system uses a local fine-tuned Hugging Face **DistilBERT** sequence classification model combined with a regex detection layer to detect contact information sharing or circumvention attempts in real-time chat.

---

## 🚀 How to Start the Project

To run this project, you need to set up the Python virtual environment, install the required packages, and run the centralized startup script.

### 1. Activating the Virtual Environment

Before running any script, you must activate the project's pre-configured virtual environment (`.venv`).

#### **On Windows:**
* Open PowerShell or CMD in the project root directory.
* **PowerShell:**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
  *(If you get a script execution policy error, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first)*
* **Command Prompt (CMD):**
  ```cmd
  .\.venv\Scripts\activate.bat
  ```

#### **On Ubuntu / Linux:**
* Open your terminal in the project root directory and run:
  ```bash
  source .venv/bin/activate
  ```

---

### 2. Installing Dependencies
With the virtual environment activated, install all necessary Python packages:
```bash
pip install -r requirements.txt
```

---

### 3. Running the Centralized Services
To start all required backends, run the main startup controller located at the project root:
```bash
python filter_chat.py
```
This script launches all three internal services in parallel within a single terminal:
1. **Filter Model Server** on port `9901`
2. **Automation API Server** on port `9500`
3. **Chat Server** on port `9800`

Pressing `Ctrl + C` in the terminal will safely terminate all three processes.

---

### 4. Testing the Chat Filtration Interface
Once the services are active, navigate your browser to the following target URL to check and test the chat filtration system:
👉 **[http://localhost:9800/filter.html](http://localhost:9800/filter.html)**

---

## 📂 Project Architecture & File Breakdown

Below is the breakdown of the primary codebase files and their corresponding responsibilities:

### 1. Centralized Startup
* **[filter_chat.py](file:///D:/Main/5-May/graveyard/relayondemand-latest-main-zip-organized/filter_chat.py)**: Spawns the model inference server, the browser automation API server, and the chat server concurrently. It tracks process health and automatically shuts down all servers gracefully if you hit `Ctrl+C` or if one of the background services exits unexpectedly.

### 2. Inner Services (in `important_files/`)
* **[important_files/runs.py](file:///D:/Main/5-May/graveyard/relayondemand-latest-main-zip-organized/important_files/runs.py)**: The **Model Inference API Server** (Flask, port `9901`).
  * Loads the fine-tuned DistilBERT classification model and tokenizer into memory once on startup.
  * Uses a robust Regex layer first to catch obvious emails, obfuscated emails (e.g. `at`, `dot`), standard phone formats, and split digits.
  * Implements an automatic filter that ignores numbers associated with common logistic units (like `lbs`, `miles`, `kg`, `hrs`, `am/pm`) to prevent false-positive contact detections on typical shipping/trucking details.
  * Houses the `/predict` and `/clear_history` POST routes, maintaining the sliding window history of the last 5 clean messages per user to evaluate split numbers.
* **[important_files/api_server.py](file:///D:/Main/5-May/graveyard/relayondemand-latest-main-zip-organized/important_files/api_server.py)**: The **Carrier Automation API Server** (Flask, port `9500`).
  * Exposes web automation endpoints (`/api/*`) that execute a background Playwright script (`automation.py`) for page-level DOM analysis, navigation, form submission, and screenshots.
  * Exposes direct HTTP v2 backend endpoints (`/api/v2/*`) to interact with the target carrier application securely and quickly.
  * Incorporates model retraining endpoints (`/api/train` and `/api/train/status`) to trigger the dataset fine-tuning process.
* **[important_files/chat_server.py](file:///D:/Main/5-May/graveyard/relayondemand-latest-main-zip-organized/important_files/chat_server.py)**: The **Chat Gateway & Web Server** (Flask, port `9800`).
  * Serves frontend files from the `web_interface/` directory (e.g., `filter.html`, `automation_chat.html`).
  * Acts as a CORS reverse-proxy forwarding commands from the UI to the Automation API.
  * Integrates with the model server on port `9901` through `/api/filter` to classify incoming messages and return safety status, reason codes, category labels, and confidence metrics.
  * Implements automated server-side message history TTL (auto-expires stale user session caches after 30 minutes of inactivity).
* **[important_files/train_model.py](file:///D:/Main/5-May/graveyard/relayondemand-latest-main-zip-organized/important_files/train_model.py)**: The model training script.
  * Loads training examples from the local CSV file `important_files/data/contact_dataset_20k_v3.csv`.
  * Fine-tunes the pretrained `distilbert-base-uncased` transformer on binary classification (contact information vs clean messages).
  * Automatically saves the trained state, config file, and tokenizer settings into the `important_files/model` directory.

---

## 🧠 Model Directory (`important_files/model/`)

The **[important_files/model](file:///D:/Main/5-May/graveyard/relayondemand-latest-main-zip-organized/important_files/model)** folder contains the weights, configs, and checkpoint history for the trained neural network classifier:

1. **`model.safetensors`**: The fine-tuned Hugging Face transformer model parameter weights. Stored in the secure and rapid `safetensors` binary format (~268MB).
2. **`config.json`**: The Hugging Face `PretrainedConfig` JSON specifying model parameters, layer dimensions (6 layers, 12 attention heads, hidden dim of 768), dropout rates, and target output label classes (`num_labels=2`).
3. **`tokenizer.json` & `tokenizer_config.json`**: Stores the token-to-integer mapping (vocab size of 30,522) and configuration settings (e.g., truncation settings, padding character ids, special token identifiers like `[CLS]` and `[SEP]`) that clean and encode raw input strings into numerical tensor formats suitable for the neural network.
4. **`checkpoint-1125 / checkpoint-2250 / checkpoint-3375`**: Subfolders containing intermediate training epochs' weights, training parameters, optimizer states, and history logs, allowing the developer to trace training convergence or resume training from where it left off.
