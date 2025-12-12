# pc_control_tools.py
"""
PC control utilities (BCMM-based mouse + keyboard).
- Mock-friendly but production-ready toggles for real execution.
- BCMM: Minimum-Jerk time-scaling + OU jitter + optional elliptical bias.
- Use set_real_mode(True) to enable actual pyautogui/pynput calls.

NOTE: To use real hardware control you must `pip install pyautogui pynput`
and run with proper OS permissions.
"""

from __future__ import annotations
import time
import math
import random
from typing import Dict, Any, Tuple, Optional

# ---- CONFIG / HYPERPARAMS ----
TF_MIN = 0.35
TF_MAX = 0.55
DT = 0.008  # sample step in seconds
OU_KAPPA = 30.0
OU_SIGMA = 1.0

# Ellipse default: curvature factor 0.0 => straight line. 0.2 small curve, 0.5 large.
DEFAULT_ELLIPSE_CURVATURE = 0.18

# Safety / bounds (can be updated at runtime by calling set_screen_bounds)
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

# Execution mode
_REAL_MODE = False

# Abort token (set True to stop current movement)
_abort_flag = False

# RNG seed for reproducibility
_RNG_SEED: Optional[int] = None

# Import optional libs at runtime if real mode enabled
_pyautogui = None
_pynput = None

# -------------------------------

def set_real_mode(enable: bool):
    """Enable/disable real input using pyautogui/pynput. Safe default: False."""
    global _REAL_MODE, _pyautogui, _pynput
    _REAL_MODE = bool(enable)
    if _REAL_MODE:
        try:
            import pyautogui as _pg
            from pynput.keyboard import Controller as _KeyboardController, Key as _Key
            _pyautogui = _pg
            _pynput = (_KeyboardController(), _Key)
            # Optional: disable pyautogui failsafe if needed
            _pyautogui.FAILSAFE = False
        except Exception as e:
            _REAL_MODE = False
            _pyautogui = None
            _pynput = None
            raise RuntimeError("Failed to enable real mode. Install pyautogui and pynput.") from e

def set_screen_bounds(width: int, height: int):
    """Set screen bounds for safety/clamping (pixels)."""
    global SCREEN_WIDTH, SCREEN_HEIGHT
    SCREEN_WIDTH = max(100, int(width))
    SCREEN_HEIGHT = max(100, int(height))

def set_seed(seed: Optional[int]):
    """Set RNG seed for reproducible motion (useful for tests)."""
    global _RNG_SEED
    _RNG_SEED = None if seed is None else int(seed)
    random.seed(_RNG_SEED)

def abort_current_motion():
    """Signal to stop any running movement as soon as possible."""
    global _abort_flag
    _abort_flag = True

def clear_abort_flag():
    global _abort_flag
    _abort_flag = False

def _minimum_jerk_scaling(t: float, Tf: float) -> float:
    t_norm = max(0.0, min(1.0, t / Tf))
    return 10.0 * t_norm**3 - 15.0 * t_norm**4 + 6.0 * t_norm**5

def _clamp_coord(x: int, y: int) -> Tuple[int, int]:
    cx = int(max(0, min(SCREEN_WIDTH - 1, x)))
    cy = int(max(0, min(SCREEN_HEIGHT - 1, y)))
    return cx, cy

def _compute_tf_by_distance(distance: float, a: float = TF_MIN, b: float = TF_MAX) -> float:
    """
    Simple distance-based Tf scaling (proxy to Fitts' law).
    Returns Tf in [TF_MIN, TF_MAX].
    """
    # distance normalized: assume typical screen distance 1000 pixels for scaling
    norm = distance / 1000.0
    Tf = a + norm * (b - a)
    return max(a, min(b, Tf))

def _elliptical_point(start: Tuple[float, float], target: Tuple[float, float],
                      s: float, curvature: float) -> Tuple[float, float]:
    """
    Return a point along an elliptical-biased arc between start and target.
    curvature: 0.0 -> straight line; positive -> bulge to the left of path vector; negative -> right
    """
    sx, sy = start
    tx, ty = target
    mx, my = (sx + tx) / 2.0, (sy + ty) / 2.0  # midpoint
    vx, vy = tx - sx, ty - sy
    dist = math.hypot(vx, vy)
    if dist < 1e-6 or abs(curvature) < 1e-6:
        # fallback to linear interpolation
        return sx + vx * s, sy + vy * s

    # perpendicular unit vector (left-hand)
    perp_x, perp_y = -vy / dist, vx / dist

    # bulge magnitude proportional to curvature * dist
    h = curvature * dist

    # ellipse parameterization by s (0..1) mapped to angle theta
    # simple quadratic bulge: pos = linear + perp * h * (4*s*(1-s)) -> symmetric bulge
    linear_x = sx + vx * s
    linear_y = sy + vy * s
    bulge_factor = 4.0 * s * (1.0 - s)  # peaks at s=0.5
    bx = linear_x + perp_x * h * bulge_factor
    by = linear_y + perp_y * h * bulge_factor
    return bx, by

def _move_cursor_to(x: int, y: int):
    """Move cursor to (x,y) immediately (real or mock)."""
    if _REAL_MODE and _pyautogui is not None:
        _pyautogui.moveTo(x, y, duration=0)  # immediate move; BCMM controls timing
    else:
        # Mock: no-op (we rely on timing to simulate motion)
        pass

def _click_at(x: int, y: int, button: str = "left"):
    if _REAL_MODE and _pyautogui is not None:
        _pyautogui.click(x=x, y=y, button=button)
    else:
        # mock click: no-op
        pass

def _press_key(key: str, modifier: Optional[str] = None):
    if _REAL_MODE and _pynput is not None:
        keyboard_ctrl, Key = _pynput
        if modifier:
            mod = getattr(Key, modifier, None)
            if mod:
                keyboard_ctrl.press(mod)
        keyboard_ctrl.press(key)
        keyboard_ctrl.release(key)
        if modifier and mod:
            keyboard_ctrl.release(mod)
    else:
        # mock: no-op
        pass

# -------------------------
# Core BCMM move function
# -------------------------
def bcmm_move(start_x: int, start_y: int, target_x: int, target_y: int,
              ellipse_curvature: float = DEFAULT_ELLIPSE_CURVATURE,
              tf_override: Optional[float] = None,
              dt: float = DT) -> Dict[str, Any]:
    """
    Execute a BCMM mouse move from (start_x,start_y) to (target_x,target_y).
    Returns a summary dict with stats.
    - ellipse_curvature: 0 -> straight; >0 -> bulge left; <0 -> bulge right
    - tf_override: if provided, uses that total movement time (clamped)
    - dt: sampling timestep (seconds)
    """
    global _abort_flag
    if _RNG_SEED is not None:
        random.seed(_RNG_SEED)

    sx, sy = _clamp_coord(int(start_x), int(start_y))
    tx, ty = _clamp_coord(int(target_x), int(target_y))
    dx = tx - sx
    dy = ty - sy
    distance = math.hypot(dx, dy)

    Tf = _compute_tf_by_distance(distance) if tf_override is None else max(TF_MIN, min(TF_MAX, tf_override))
    steps = max(2, int(max(1, round(Tf / dt))))
    jitter_x, jitter_y = 0.0, 0.0
    OU_CONST = 1.0 - (OU_KAPPA * dt)
    SIGMA_CONST = OU_SIGMA * math.sqrt(dt)

    start_time = time.perf_counter()
    last_tick = start_time
    for i in range(1, steps + 1):
        if _abort_flag:
            # Movement aborted
            clear_abort_flag()
            return {"ok": False, "message": "aborted", "progress_step": i - 1, "steps": steps}

        t = i * dt
        s_t = _minimum_jerk_scaling(t, Tf)

        # deterministic (elliptical bias)
        cur_xf, cur_yf = _elliptical_point((sx, sy), (tx, ty), s_t, ellipse_curvature)

        # OU jitter update
        jitter_x = jitter_x * OU_CONST + SIGMA_CONST * random.gauss(0.0, 1.0)
        jitter_y = jitter_y * OU_CONST + SIGMA_CONST * random.gauss(0.0, 1.0)

        # Final position
        final_x = int(round(cur_xf + jitter_x))
        final_y = int(round(cur_yf + jitter_y))
        final_x, final_y = _clamp_coord(final_x, final_y)

        # Move cursor (or mock)
        _move_cursor_to(final_x, final_y)

        # Maintain precise timing
        # sleep until the next tick using perf_counter
        now = time.perf_counter()
        elapsed = now - last_tick
        wait = dt - elapsed
        if wait > 0:
            time.sleep(wait)
        last_tick = time.perf_counter()

    # Final snap to the exact target to ensure precision
    _move_cursor_to(tx, ty)

    return {
        "ok": True,
        "message": "moved",
        "start": {"x": sx, "y": sy},
        "target": {"x": tx, "y": ty},
        "distance": distance,
        "Tf": Tf,
        "steps": steps
    }

# -------------------------
# Tool wrappers
# -------------------------
def tool_mouse_click(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Args:
      - x (int), y (int) required
      - button (str): 'left'|'right'|'middle'
      - start_x, start_y (optional) override
      - curvature (float, optional): elliptical curvature
      - tf (float, optional): override Tf
    """
    x = args.get("x")
    y = args.get("y")
    
    # In a real environment, you should get the current position dynamically if start_x/y aren't provided
    start_x = args.get("start_x", _pyautogui.position()[0] if _REAL_MODE and _pyautogui else 500)
    start_y = args.get("start_y", _pyautogui.position()[1] if _REAL_MODE and _pyautogui else 500)
    
    if x is None or y is None:
        return {"ok": False, "message": "Missing x or y"}

    button = args.get("button", "left")
    curvature = float(args.get("curvature", DEFAULT_ELLIPSE_CURVATURE))
    tf = args.get("tf", None)

    summary = bcmm_move(start_x, start_y, x, y, ellipse_curvature=curvature, tf_override=tf)
    if not summary.get("ok"):
        return summary

    # perform click
    _click_at(x, y, button=button)

    return {
        "ok": True,
        "message": f"BCMM Click executed at ({x},{y})",
        "summary": summary,
        "coordinates": {"x": x, "y": y, "button": button}
    }

def tool_keyboard_press(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Args:
      - key (str) required
      - modifier (str) optional (ctrl, alt, shift)
    """
    key = (args.get("key") or "").strip()
    modifier = (args.get("modifier") or "").strip() or None
    if not key:
        return {"ok": False, "message": "Missing key"}

    # In real mode, this will press the key using pynput; mock mode returns success
    _press_key(key, modifier)
    return {"ok": True, "message": f"pressed {modifier + '+' if modifier else ''}{key}"}

# Registry for external use
TOOL_REGISTRY_PC_CONTROL = {
    "mouse_click": tool_mouse_click,
    "keyboard_press": tool_keyboard_press,
}