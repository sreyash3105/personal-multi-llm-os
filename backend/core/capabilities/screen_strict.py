"""
STRICT SCREEN CAPABILITY

Capability: screen.capture (READ-ONLY)
No inference. No defaults. Refusal-first.

Build Prompt: CAPABILITY EXPANSION UNDER MEK
"""

from __future__ import annotations

import time
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ScreenRefusal(Enum):
    REGION_INVALID = "region_invalid"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UNSPECIFIED_REGION = "unspecified_region"


class ScreenError(RuntimeError):
    def __init__(self, refusal: ScreenRefusal, details: str):
        self.refusal = refusal
        self.details = details
        super().__init__(f"[{refusal.value}] {details}")


MAX_WIDTH = 3840
MAX_HEIGHT = 2160
MIN_RATE_LIMIT_MS = 1000


@dataclass(frozen=True)
class ScreenConfig:
    max_width: int = MAX_WIDTH
    max_height: int = MAX_HEIGHT
    min_rate_limit_ms: int = MIN_RATE_LIMIT_MS
    allow_full_screen: bool = True
    forbid_continuous_capture: bool = True


_last_capture_time: float = 0
_last_capture_lock = object()


def validate_rate_limit(config: ScreenConfig) -> None:
    global _last_capture_time, _last_capture_lock

    now = time.time()
    elapsed_ms = (now - _last_capture_time) * 1000

    if elapsed_ms < config.min_rate_limit_ms:
        raise ScreenError(
            ScreenRefusal.RATE_LIMIT_EXCEEDED,
            f"Rate limit exceeded. Last capture {elapsed_ms:.0f}ms ago, "
            f"minimum {config.min_rate_limit_ms}ms required"
        )

    _last_capture_time = now


def validate_region(
    region: Optional[Tuple[int, int, int, int]],
    config: ScreenConfig,
) -> Tuple[int, int, int, int]:
    if region is None:
        if config.allow_full_screen:
            try:
                import screeninfo
                monitor = screeninfo.get_monitors()[0]
                return (0, 0, monitor.width, monitor.height)
            except Exception:
                return (0, 0, 1920, 1080)
        else:
            raise ScreenError(
                ScreenRefusal.UNSPECIFIED_REGION,
                "Region must be specified when full-screen capture disabled"
            )

    if len(region) != 4:
        raise ScreenError(
            ScreenRefusal.REGION_INVALID,
            f"Region must have 4 values (x, y, width, height), got {len(region)}"
        )

    x, y, width, height = region

    if width <= 0 or height <= 0:
        raise ScreenError(
            ScreenRefusal.REGION_INVALID,
            f"Invalid region dimensions: {width}x{height}"
        )

    if width > config.max_width:
        raise ScreenError(
            ScreenRefusal.REGION_INVALID,
            f"Region width {width} exceeds limit {config.max_width}"
        )

    if height > config.max_height:
        raise ScreenError(
            ScreenRefusal.REGION_INVALID,
            f"Region height {height} exceeds limit {config.max_height}"
        )

    return (x, y, width, height)


class ScreenCapture:
    consequence_level = "LOW"
    required_fields = []

    @staticmethod
    def execute(
        context: Dict[str, Any],
        config: Optional[ScreenConfig] = None,
    ) -> Dict[str, Any]:
        config = config or ScreenConfig()

        validate_rate_limit(config)

        region = context.get("region")
        x, y, width, height = validate_region(region, config)

        try:
            from backend.modules.tools.pc_control_tools import take_screenshot as capture_screen

            result = capture_screen({"region": (x, y, width, height)})

            if result.get("status") == "refused":
                raise ScreenError(
                    ScreenRefusal.REGION_INVALID,
                    result.get("explanation", "Screenshot capture refused")
                )

            return {
                "region": (x, y, width, height),
                "status": result.get("status"),
                "path": result.get("path"),
                "size": result.get("size"),
            }
        except Exception as e:
            raise ScreenError(
                ScreenRefusal.REGION_INVALID,
                f"Failed to capture screen: {e}"
            )
