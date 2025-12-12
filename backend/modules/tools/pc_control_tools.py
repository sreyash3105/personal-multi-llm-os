"""
pc_control_tools.py

Tools for full PC control (Mouse Autonomy and Keyboard Autonomy).
These tools are deliberately segregated from file_tools.py due to their high risk profile.

NOTE: These functions require a system-level library like 'pyautogui' or 'pynput'
to be installed in your local environment and MUST be run in a privileged process.
"""

from typing import Dict, Any, List

# --- MOCK IMPLEMENTATION WARNING ---
# Actual mouse/keyboard control is system-dependent and outside the sandbox.
# Replace the mocks below with real pynput/pyautogui calls on your local machine.

def tool_mouse_click(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulates a mouse click at specific coordinates.
    The planner should avoid raw coordinates if possible, preferring selectors.

    Args:
      - x (int, required): X coordinate.
      - y (int, required): Y coordinate.
      - button (str, optional): 'left' (default), 'right', 'middle'.
    """
    x = args.get("x")
    y = args.get("y")
    button = args.get("button", "left").lower()

    if x is None or y is None:
        return {"ok": False, "message": "Missing required 'x' or 'y' coordinates."}

    # --- MOCK: In a real environment, you would call: ---
    # import pyautogui
    # pyautogui.click(x=x, y=y, button=button)
    # -----------------------------------------------------

    return {
        "ok": True,
        "message": f"Mouse click simulated at ({x}, {y}) with '{button}' button.",
        "action": "mouse_click",
        "coordinates": {"x": x, "y": y, "button": button}
    }


def tool_keyboard_press(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulates a key press, or a combination of keys (chords/hotkeys).

    Args:
      - key (str, required): The key to press (e.g., 'enter', 'space', 'c').
      - modifier (str, optional): A modifier key (e.g., 'ctrl', 'alt', 'shift').
    """
    key = (args.get("key") or "").strip()
    modifier = (args.get("modifier") or "").strip()

    if not key:
        return {"ok": False, "message": "Missing required 'key' argument."}

    # --- MOCK: In a real environment, you would call: ---
    # from pynput.keyboard import Key, Controller
    # keyboard = Controller()
    # if modifier:
    #     with keyboard.pressed(modifier_map.get(modifier)):
    #         keyboard.press(key_map.get(key, key))
    # else:
    #     keyboard.press(key_map.get(key, key))
    # -----------------------------------------------------

    action = f"{modifier}+{key}" if modifier else key

    return {
        "ok": True,
        "message": f"Keyboard press simulated: '{action}'.",
        "action": "keyboard_press",
        "keys": action
    }


TOOL_REGISTRY_PC_CONTROL = {
    "mouse_click": tool_mouse_click,
    "keyboard_press": tool_keyboard_press,
}