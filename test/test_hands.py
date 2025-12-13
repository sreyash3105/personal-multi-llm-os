import sys
import time
import logging
from pathlib import Path

# Ensure backend can be imported
sys.path.append(str(Path(__file__).parent))

# Import the tools
from backend.modules.tools.pc_control_tools import (
    set_real_mode,
    set_screen_bounds,
    tool_mouse_click,
    tool_keyboard_press,
    bcmm_move
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("test_hands")

def test_hands():
    print("\n🙌 WAKING UP DIGITAL HANDS...\n")

    try:
        # 1. Enable Real Mode (This hooks into pyautogui/pynput)
        set_real_mode(True)
        # Set bounds (standard 1080p, safe default)
        set_screen_bounds(1920, 1080)
        print("✅ Drivers Loaded (Real Mode: ON)")
    except Exception as e:
        print(f"❌ Failed to load drivers: {e}")
        print("   Did you run: pip install pyautogui pynput")
        return

    print("\n⚠️  WARNING: MOUSE WILL MOVE IN 3 SECONDS. LET GO OF YOUR MOUSE.")
    time.sleep(3)

    # 2. Test Mouse Movement (BCMM Physics)
    print("\n🖱️  Testing Mouse (S-Curve Physics)...")
    
    # Square movement pattern
    start_x, start_y = 500, 500
    points = [
        (800, 500), # Right
        (800, 800), # Down
        (500, 800), # Left
        (500, 500)  # Up (Home)
    ]

    # Move to start first
    bcmm_move(500, 500, start_x, start_y, tf_override=0.5)

    for i, (tx, ty) in enumerate(points):
        print(f"   -> Moving to ({tx}, {ty})...")
        # Simulate a click command (which includes the move)
        # We pass start_x/y explicitly for the test loop continuity
        result = tool_mouse_click({
            "x": tx, 
            "y": ty, 
            "start_x": start_x, 
            "start_y": start_y,
            "tf": 0.6  # Speed (0.6s per move)
        })
        
        if not result.get("ok"):
            print(f"❌ Move failed: {result}")
            break
            
        start_x, start_y = tx, ty
        time.sleep(0.2)

    print("✅ Mouse Test Complete.")

    # 3. Test Keyboard
    print("\n⌨️  Testing Keyboard...")
    print("   (Will type 'hello' into active window - DON'T CHANGE FOCUS)")
    time.sleep(1)
    
    test_str = "hello"
    for char in test_str:
        res = tool_keyboard_press({"key": char})
        if res.get("ok"):
            print(f"   Typed: '{char}'")
            time.sleep(0.1)
        else:
            print(f"❌ Failed to type '{char}'")

    print("\n✅ Keyboard Test Complete.")

if __name__ == "__main__":
    test_hands()