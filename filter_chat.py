import subprocess
import sys
import time
import signal
import os

# Store processes to manage them
processes = []

def signal_handler(sig, frame):
    """Gracefully shut down all processes on Ctrl+C."""
    print("\n\n[System] Shutting down all services...")
    for p in processes:
        try:
            p.terminate()
        except Exception as e:
            print(f"Error terminating process: {e}")
    print("[System] All services stopped.")
    sys.exit(0)

# Register the signal handler for Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

def start_services():
    # Use the same Python interpreter currently running this script
    python_exe = sys.executable
    
    # Get current root directory
    root_dir = os.getcwd()
    base_dir = os.path.join(root_dir, "important_files")
    web_dir = os.path.join(root_dir, "web_interface")

    # Define the servers to start using absolute paths
    # Order: Model -> API -> Chat
    servers = [
        {"name": "Filter Model", "cmd": [python_exe, os.path.join(base_dir, "runs.py")], "port": 9901},
        {"name": "Automation API", "cmd": [python_exe, os.path.join(base_dir, "api_server.py")], "port": 9500},
        {"name": "Chat Server", "cmd": [python_exe, os.path.join(base_dir, "chat_server.py")], "port": 9800}
    ]

    print("=" * 60)
    print("  Relay On Demand - Centralized Startup")
    print("=" * 60)
    print()

    for server in servers:
        print(f"[Starting] {server['name']} on port {server['port']}...")
        try:
            # Chat Server needs to run in web_interface to serve HTML files
            # Others run in important_files to find model/data/scripts correctly
            if server['name'] == "Chat Server":
                cwd = web_dir
            else:
                cwd = base_dir
            
            p = subprocess.Popen(server['cmd'], cwd=cwd)
            processes.append(p)
            # Short sleep to prevent port collision races and let logs initialize
            time.sleep(2)
        except Exception as e:
            print(f"[Error] Failed to start {server['name']}: {e}")

    print("\n" + "=" * 60)
    print("  SUCCESS: All services are running in this terminal!")
    print("  - Filter: http://localhost:9901")
    print("  - API:    http://localhost:9500")
    print("  - Chat:   http://localhost:9800")
    print("\n  Press Ctrl+C to STOP all services.")
    print("=" * 60 + "\n")

    # Keep the script alive and monitor processes
    try:
        while True:
            for p in processes:
                if p.poll() is not None:
                    print(f"\n[Warning] A process has exited unexpectedly.")
                    signal_handler(None, None)
            time.sleep(1)
    except KeyboardInterrupt:
        pass # Signal handler will take care of it

if __name__ == "__main__":
    start_services()
