import sys
import json
import logging
import time
from pathlib import Path

# Ensure backend can be imported
sys.path.append(str(Path(__file__).parent))

from backend.modules.vision.screen_locator import screen_locator
from backend.core.config import VISION_MODEL_NAME

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

def test_eyes():
    print(f"\n👁️  WAKING UP VISION SYSTEM (Model: {VISION_MODEL_NAME})...\n")
    
    # 1. Define a target that is definitely on your screen
    # "Taskbar" or "Start button" are good defaults for Windows
    target = "Start button" 
    command = f"Find the {target} and give me coordinates to click it."

    print(f"📸  Capturing Screen...")
    print(f"📝  Prompt: '{command}'")
    print("⏳  Analyzing (this involves sending a screenshot to LLaVA, may take 5-10s)...")

    start = time.time()
    try:
        # Run the actual locator logic
        result = screen_locator.locate_and_plan(command)
        duration = time.time() - start

        # Check results
        if not result.get("ok"):
            print(f"\n❌ Vision Failed: {result.get('error')}")
            if "raw_vision" in result:
                print(f"   Raw Model Output: {result['raw_vision'][:200]}...")
            return

        coords = result.get("coordinates")
        conf = result.get("confidence")
        
        print(f"\n✅ Vision Successful ({duration:.2f}s)")
        print(f"   Target: {target}")
        print(f"   Coordinates Found: {coords}")
        print(f"   Confidence: {conf}")
        print(f"   Reasoning: {result.get('reasoning')}")

        if coords and isinstance(coords, (list, tuple)):
            print("\n👀  VERIFICATION: Does that coordinate look correct?")
            print(f"    (It should be near the bottom-left/center for the Start button)")

    except Exception as e:
        print(f"\n❌ Vision Crashed: {e}")
        print("   (Check if Ollama is running and 'llava-phi3' is pulled)")

if __name__ == "__main__":
    test_eyes()