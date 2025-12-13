import subprocess
import time
import sys
import os
import threading

def start_server():
    # Launches the API Server (The Eyes)
    # We use sys.executable to ensure it uses the bundled Python environment
    subprocess.call([sys.executable, "backend/code_server.py"])

def start_dashboard():
    # Launches the Dashboard (The Monitor)
    time.sleep(2) # Wait for server to warm up
    subprocess.Popen([sys.executable, "dashboard_app.py"])

def start_agent():
    # Launches the Ghost Agent (The Hands)
    time.sleep(3) # Wait for server
    subprocess.call([sys.executable, "ghost_agent.py"])

if __name__ == "__main__":
    print(">>> INITIALIZING GHOST OS...")
    
    # 1. Start Server in a separate thread so it doesn't block
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # 2. Start Dashboard
    start_dashboard()

    # 3. Start Agent (Main blocking process)
    # When you close the Agent overlay, the exe will close
    start_agent()