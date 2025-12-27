"""
desktop_app.py - DEPRECATED

This desktop app previously provided a PyWebView interface to the FastAPI HTTP server.
Since the HTTP layer has been removed, this application is no longer functional.
"""

import sys

def main():
    print("=" * 60)
    print("AIOS DESKTOP APP - DEPRECATED")
    print("=" * 60)
    print()
    print("The FastAPI HTTP layer has been removed from AIOS.")
    print("The desktop PyWebView app is no longer supported.")
    print()
    print("AIOS now runs locally via direct function calls.")
    print()
    print("To use AIOS:")
    print("  1. Import backend.core.local_runner in your code")
    print("  2. Call get_runner().execute_*() methods")
    print()
    print("Example:")
    print("  from backend.core.local_runner import get_runner")
    print("  runner = get_runner()")
    print("  result = runner.execute_code('hello world')")
    print()
    print("For interactive use, create a Python script that imports and uses the local runner.")
    print("=" * 60)

if __name__ == "__main__":
    main()