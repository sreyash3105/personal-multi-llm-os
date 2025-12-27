import subprocess
import time
import sys
import os
import threading
import signal
import atexit

# Global process handles for cleanup
server_process = None
agent_process = None

def cleanup_processes():
    """Clean up subprocesses on exit."""
    if server_process and server_process.poll() is None:
        server_process.terminate()
        server_process.wait()
    if agent_process and agent_process.poll() is None:
        agent_process.terminate()
        agent_process.wait()

def signal_handler(signum, frame):
    """Handle signals for clean shutdown."""
    cleanup_processes()
    sys.exit(0)

def start_server():
    # Launches the API Server (The Eyes)
    global server_process
    try:
        server_process = subprocess.Popen([sys.executable, "backend/code_server.py"])
        returncode = server_process.wait()  # Block the thread until server exits
        if returncode != 0:
            print(f"[LAUNCHER] Server exited with code {returncode}")
    except Exception as e:
        print(f"[LAUNCHER] Failed to start server: {e}")
        server_process = None

def start_desktop_app():
    # Launches the Desktop Chat App (The Interface)
    global agent_process
    time.sleep(3) # Wait for server
    try:
        agent_process = subprocess.Popen([sys.executable, "desktop_app.py"])
        returncode = agent_process.wait()  # Block main thread until app exits
        if returncode != 0:
            print(f"[LAUNCHER] Desktop app exited with code {returncode}")
    except Exception as e:
        print(f"[LAUNCHER] Failed to start desktop app: {e}")
        agent_process = None

if __name__ == "__main__":
    # Register cleanup handlers
    atexit.register(cleanup_processes)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(">>> INITIALIZING AIOS DESKTOP...")
    print(">>> Starting backend server...")
    
    # 1. Start Backend Server in a separate thread so it doesn't block
    server_thread = threading.Thread(target=start_server)
    server_thread.start()

    print(">>> Starting desktop chat app...")
    # 2. Start Desktop Chat App (Main blocking process)
    # When you close the app window, the exe will close
    start_desktop_app()