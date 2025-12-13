"""
screen_locator.py (REAL IMPLEMENTATION)

Purpose:
- Captures the current screen.
- Sends the image + user command to the Vision Model (LLaVA).
- Asks LLaVA to estimate the (x, y) coordinates of the target UI element.
"""

import logging
import json
import re
from typing import Dict, Any, Optional, Tuple

# 3rd party
import pyautogui
import io

# Local modules
from backend.modules.vision.vision_pipeline import run_vision
from backend.core.config import VISION_MODEL_NAME

log = logging.getLogger("screen_locator")

class ScreenLocator:
    """
    Real Vision service: Screenshot -> LLaVA -> Coordinates
    """
    def locate_and_plan(self, command: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
        """
        1. Capture screenshot.
        2. Ask LLaVA: "Where is the [Save Button] in this image?"
        3. Parse JSON coordinates.
        """
        log.info(f"👀 Vision scanning for command: '{command}'")

        # 1. Capture Screen
        try:
            screenshot = pyautogui.screenshot()
            img_byte_arr = io.BytesIO()
            screenshot.save(img_byte_arr, format='PNG')
            image_bytes = img_byte_arr.getvalue()
            
            screen_w, screen_h = screenshot.size
        except Exception as e:
            return {"ok": False, "error": f"Screenshot failed: {e}"}

        # 2. Construct Prompt for LLaVA
        # We ask for a normalized 0-1000 scale to be robust against resolution changes
        prompt = (
            f"User command: '{command}'.\n"
            "Analyze the UI in this image. Locate the specific element the user wants to interact with.\n"
            "Return a SINGLE JSON object with the center coordinates of that element.\n"
            "Use a 1000x1000 coordinate system (0,0 is top-left, 1000,1000 is bottom-right).\n\n"
            "Format:\n"
            "{\n"
            '  "element_name": "Save Button",\n'
            '  "x_1000": 500,\n'
            '  "y_1000": 500,\n'
            '  "confidence": 0.9\n'
            "}"
        )

        # 3. Call Vision Pipeline
        vision_response = run_vision(
            image_bytes=image_bytes,
            user_prompt=prompt,
            mode="code", # 'code' mode usually reduces hallucinations
            model_name=VISION_MODEL_NAME
        )

        # 4. Parse Coordinates
        parsed = self._extract_json(vision_response)
        
        if not parsed or "x_1000" not in parsed:
            log.warning(f"Vision failed to find element. Response: {vision_response[:100]}")
            return {
                "ok": False, 
                "error": "Could not locate element visually.", 
                "raw_vision": vision_response
            }

        # 5. Scale to real screen resolution
        target_x = int((parsed["x_1000"] / 1000.0) * screen_w)
        target_y = int((parsed["y_1000"] / 1000.0) * screen_h)

        log.info(f"🎯 Target Acquired: {parsed.get('element_name')} at ({target_x}, {target_y})")

        return {
            "ok": True,
            "action": "mouse_click",
            "coordinates": (target_x, target_y),
            "confidence": parsed.get("confidence", 0.5),
            "reasoning": f"Visual match for {parsed.get('element_name')}",
            "tool_name": "screen_locator",
        }

    def _extract_json(self, text: str) -> Optional[Dict]:
        """Helper to find JSON blob in LLM response."""
        try:
            # Look for { ... }
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except:
            pass
        return None

# Singleton
screen_locator = ScreenLocator()

def locate_action_plan(command: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
    return screen_locator.locate_and_plan(command, profile_id)