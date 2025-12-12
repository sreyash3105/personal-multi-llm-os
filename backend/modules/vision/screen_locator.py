"""
screen_locator.py

Specialized vision service extension for Full PC Control (Plan Sections 10 & 11).

Purpose:
- Takes a natural language command (e.g., "Click the Save button") and a visual
  context (mocked here, but would be image bytes + OCR in a real app).
- Locates the target element.
- Returns a structured action plan with coordinates/selectors.
"""

from typing import Dict, Any, Optional
import logging
import random

log = logging.getLogger("screen_locator")

# --- MOCK IMPLEMENTATION WARNING ---
# In a real environment, this service would call a local LLaVA/GPT4-V model
# with the screenshot and prompt to get a JSON output containing the coordinates.

class ScreenLocator:
    """
    Simulates the logic of an LLM/Vision model locating elements on a screen.
    """
    def locate_and_plan(self, command: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes a user command against a hypothetical screen state.

        Returns:
          {
            "ok": bool,
            "action": str,         # mouse_click, keyboard_type, scroll_to
            "coordinates": tuple,  # (x, y) if click/move
            "confidence": float,   # 0.0 to 1.0
            "reasoning": str
          }
        """
        command_lower = command.lower()
        action = "unknown"
        coordinates = None
        confidence = 0.85
        reasoning = "Simulated location based on keyword matching."

        if "click" in command_lower or "tap" in command_lower:
            action = "mouse_click"
            # Simulate locating a button
            if "save" in command_lower:
                coordinates = (950, 50)
            elif "submit" in command_lower:
                coordinates = (800, 450)
            else:
                coordinates = (random.randint(200, 1000), random.randint(100, 700))
        
        elif "type" in command_lower or "input" in command_lower:
            action = "keyboard_type"
            confidence = 0.95
            reasoning = "Target is a common form field."
            
        elif "scroll" in command_lower or "move mouse" in command_lower:
            action = "mouse_move"
            coordinates = (random.randint(500, 800), random.randint(300, 600))
            reasoning = "Detected relative movement command."
            
        else:
            confidence = 0.5
            reasoning = "Could not identify a clear screen action."

        log.debug("Screen command processed: %s -> %s", command, action)

        return {
            "ok": True,
            "action": action,
            "coordinates": coordinates,
            "text_to_type": command_lower.split("type", 1)[-1].strip() if action == "keyboard_type" and "type" in command_lower else None,
            "confidence": confidence,
            "reasoning": reasoning,
            "tool_name": "screen_locator",
        }

# Singleton instance
screen_locator = ScreenLocator()

# Public API wrapper for convenience in the executor
def locate_action_plan(command: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
    return screen_locator.locate_and_plan(command, profile_id)