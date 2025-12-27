"""
desktop_app.py

Desktop app shell for AIOS Chat UI.
Loads the existing chat interface in a native window using PyWebView.
Acts purely as a client to the backend APIs.
"""

try:
    import webview
except ImportError:
    print("Error: PyWebView not installed. Install with: pip install pywebview")
    sys.exit(1)

import sys
import os
import time
import requests

def wait_for_server(url="http://localhost:8000/", timeout=10):
    """Wait for the backend server to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return False

def main():
    # URL of the chat UI served by the backend
    chat_url = "http://localhost:8000/"

    # Wait for server to be ready
    if not wait_for_server(chat_url):
        print("Error: Backend server not ready. Please start the server first.")
        sys.exit(1)

    # Create the webview window
    try:
        window = webview.create_window(
            title="AIOS Chat",
            url=chat_url,
            width=1200,
            height=800,
            resizable=True,
            frameless=False,
            easy_drag=False,
        )

        # Start the webview app (blocking)
        webview.start()
    except Exception as e:
        print(f"Error starting desktop app: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()