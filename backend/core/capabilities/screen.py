"""
Screen/Mouse control capability - existing logic formalized.

Single capability, explicit consequence, mandatory pattern emission.
"""

from __future__ import annotations

import time
from typing import Dict, Any, Optional

from backend.core.capability import CapabilityDescriptor, ConsequenceLevel, create_refusal, RefusalReason


try:
    from backend.modules.tools.pc_control_tools import (
        click_at,
        type_text,
        press_key,
        take_screenshot,
        is_real_mode_available,
    )
    REAL_CONTROL_AVAILABLE = True
except ImportError:
    REAL_CONTROL_AVAILABLE = False

    def click_at(x: int, y: int, context: Dict[str, Any]) -> Any:
        return {"status": "refused", "reason": "mock_mode", "explanation": "Real control not available"}

    def type_text(text: str, context: Dict[str, Any]) -> Any:
        return {"status": "refused", "reason": "mock_mode", "explanation": "Real control not available"}

    def press_key(key: str, context: Dict[str, Any]) -> Any:
        return {"status": "refused", "reason": "mock_mode", "explanation": "Real control not available"}

    def take_screenshot(context: Dict[str, Any]) -> Any:
        return {"status": "refused", "reason": "mock_mode", "explanation": "Real control not available"}


class ScreenCapability:
    """
    Screen and mouse control with explicit constraints.
    """

    def __init__(self):
        self.real_mode = REAL_CONTROL_AVAILABLE

    def _emit_pattern(self, action: str, context: Dict[str, Any]) -> None:
        """
        Emit pattern event for screen interaction.
        """
        try:
            from backend.core.pattern_event import PatternEvent, PatternType, PatternSeverity
            from backend.core.pattern_record import PatternRecord
            from backend.core.pattern_aggregator import PatternAggregator

            event = PatternEvent(
                pattern_type=PatternType.ACTION,
                severity=PatternSeverity.INFO,
                metadata={
                    "action": action,
                    "real_mode": self.real_mode,
                    "context_id": context.get("execution_context", {}).get("context_id", "unknown"),
                },
            )

            record = PatternRecord.from_event(event)
            agg = PatternAggregator()
            agg.record_pattern(record)
        except Exception as e:
            print(f"[SCREEN] Failed to emit pattern: {e}")

    def click_at(self, x: int, y: int, context: Dict[str, Any]) -> Any:
        """
        Click at screen coordinates.

        HIGH consequence → mandatory friction.
        """
        print(f"[SCREEN] Click at ({x}, {y})")

        if not self.real_mode:
            self._emit_pattern("click_mock", context)
            return click_at(x, y, context)

        result = click_at(x, y, context)

        self._emit_pattern("click", context)
        return result

    def type_text(self, text: str, context: Dict[str, Any]) -> Any:
        """
        Type text at current location.

        MEDIUM consequence → no friction.
        """
        print(f"[SCREEN] Type: {text[:50]}...")

        if not self.real_mode:
            self._emit_pattern("type_mock", context)
            return type_text(text, context)

        result = type_text(text, context)
        self._emit_pattern("type", context)
        return result

    def press_key(self, key: str, context: Dict[str, Any]) -> Any:
        """
        Press a key.

        MEDIUM consequence → no friction.
        """
        print(f"[SCREEN] Press key: {key}")

        if not self.real_mode:
            self._emit_pattern("key_mock", context)
            return press_key(key, context)

        result = press_key(key, context)
        self._emit_pattern("press_key", context)
        return result

    def capture_screen(self, context: Dict[str, Any]) -> Any:
        """
        Capture screenshot.

        LOW consequence → no friction.
        """
        print(f"[SCREEN] Capture screenshot")

        if not self.real_mode:
            self._emit_pattern("screenshot_mock", context)
            return take_screenshot(context)

        result = take_screenshot(context)
        self._emit_pattern("screenshot", context)
        return result


def create_screen_capability() -> CapabilityDescriptor:
    """
    Create the screen/mouse control capability descriptor.
    """
    cap = ScreenCapability()

    def execute(context: Dict[str, Any]) -> Any:
        action = context.get("action")

        if action == "click":
            x = context.get("x")
            y = context.get("y")
            if x is None or y is None:
                return create_refusal(
                    RefusalReason.AMBIGUITY,
                    "Click requires 'x' and 'y' fields",
                    "screen.execute",
                )
            return cap.click_at(x, y, context)

        elif action == "type":
            text = context.get("text")
            if text is None:
                return create_refusal(
                    RefusalReason.AMBIGUITY,
                    "Type requires 'text' field",
                    "screen.execute",
                )
            return cap.type_text(text, context)

        elif action == "press_key":
            key = context.get("key")
            if key is None:
                return create_refusal(
                    RefusalReason.AMBIGUITY,
                    "Press key requires 'key' field",
                    "screen.execute",
                )
            return cap.press_key(key, context)

        elif action == "screenshot":
            return cap.capture_screen(context)

        else:
            return create_refusal(
                RefusalReason.CONSTRAINT_VIOLATION,
                f"Unknown action: {action}",
                "screen.execute",
            )

    return CapabilityDescriptor(
        name="screen",
        scope="ui",
        consequence_level=ConsequenceLevel.MEDIUM,
        required_context_fields=["action"],
        required_approvals=[],
        execute_fn=execute,
    )
