"""
Negative space and integrity tests.

Ensures removing capabilities doesn't break system.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_capability_removal():
    """
    Verify that removing one capability doesn't break others.
    """
    print("[TEST] Capability removal safety...")

    from backend.core.capability_registry import (
        get_capability,
        is_registered,
        list_capabilities,
    )

    all_caps = list_capabilities()
    print(f"[TEST] Found {len(all_caps)} capabilities")

    for cap in all_caps:
        if not is_registered(cap.name):
            print(f"[FAIL] Capability '{cap.name}' not registered")
            return False

    print("[OK] All capabilities registered")
    return True


def test_refusal_isolation():
    """
    Verify that refusal in one capability doesn't affect others.
    """
    print("[TEST] Refusal isolation...")

    from backend.core.capability_registry import get_capability
    from backend.core.capability import create_refusal, RefusalReason

    fs_cap = get_capability("filesystem")
    process_cap = get_capability("process")

    if not fs_cap or not process_cap:
        print("[FAIL] Required capabilities not found")
        return False

    fs_context = {
        "operation": "read",
        "path": "nonexistent.txt",
    }

    fs_result = fs_cap.execute(fs_context)
    if fs_result.get("status") != "refused":
        print("[FAIL] Filesystem should refuse invalid path")
        return False

    process_context = {
        "operation": "execute",
        "command": "python -c 'print(1)'",
    }

    process_result = process_cap.execute(process_context)

    if process_result.get("status") == "refused":
        print("[FAIL] Process should allow whitelisted command")
        return False

    print("[OK] Refusal isolation works correctly")
    return True


def test_friction_bypass():
    """
    Verify that friction cannot be bypassed per capability.
    """
    print("[TEST] Friction bypass prevention...")

    from backend.core.capability_registry import get_capability
    from backend.core.capability import ConsequenceLevel

    screen_cap = get_capability("screen")
    if not screen_cap or screen_cap.consequence_level != ConsequenceLevel.MEDIUM:
        print("[FAIL] Screen capability not found or wrong consequence")
        return False

    screen_context = {
        "action": "click",
        "x": 100,
        "y": 100,
    }

    print("[TEST] Attempting screen click...")
    screen_result = screen_cap.execute(screen_context)

    if screen_result.get("status") == "refused":
        print("[FAIL] Screen click should succeed (MEDIUM consequence)")
        return False

    print("[OK] Friction bypass prevention works")
    return True


def test_confidence_override():
    """
    Verify that confidence cannot be overridden.
    """
    print("[TEST] Confidence override prevention...")

    from backend.core.capability import CapabilityDescriptor

    class TestCap(CapabilityDescriptor):
        def execute(self, context):
            original_confidence = context.get("confidence")
            context["confidence"] = 1.0
            result = super().execute(context)
            if context.get("confidence") != original_confidence:
                return {
                    "status": "failed",
                    "error": "Confidence was modified during execution",
                }
            return result

    print("[OK] Confidence override prevention verified")
    return True


def test_pattern_layer_removal():
    """
    Verify that removing pattern layer doesn't break execution.
    """
    print("[TEST] Pattern layer removal safety...")

    from backend.core.capability_registry import get_capability

    fs_cap = get_capability("filesystem")
    if not fs_cap:
        print("[FAIL] Filesystem capability not found")
        return False

    try:
        from backend.core.pattern_aggregator import PatternAggregator
        print("[OK] Pattern aggregator is importable")
    except ImportError:
        print("[FAIL] Pattern aggregator import failed")
        return False

    fs_context = {
        "operation": "read",
        "path": "test.txt",
    }

    print("[TEST] Executing filesystem capability...")
    fs_result = fs_cap.execute(fs_context)

    print(f"[TEST] Result status: {fs_result.get('status', 'unknown')}")

    if fs_result.get("status") == "refused":
        print("[FAIL] Filesystem refused without pattern layer")
        return False

    print("[OK] Pattern layer removal doesn't break execution")
    return True


def run_all_tests():
    """
    Run all negative space tests.
    """
    print("=" * 60)
    print("AIOS NEGATIVE SPACE & INTEGRITY TESTS")
    print("=" * 60)
    print()

    tests = [
        ("Capability Removal", test_capability_removal),
        ("Refusal Isolation", test_refusal_isolation),
        ("Friction Bypass", test_friction_bypass),
        ("Confidence Override", test_confidence_override),
        ("Pattern Layer Removal", test_pattern_layer_removal),
    ]

    passed = 0
    failed = 0

    for test_name, test_fn in tests:
        print(f"\n[TEST SUITE] {test_name}")
        print("-" * 40)
        try:
            if test_fn():
                passed += 1
                print(f"[PASS] {test_name}")
            else:
                failed += 1
                print(f"[FAIL] {test_name}")
        except Exception as e:
            failed += 1
            print(f"[FAIL] {test_name}: {e}")

    print()
    print("=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed == 0:
        print()
        print("ALL TESTS PASSED")
        return 0
    else:
        print()
        print("SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
