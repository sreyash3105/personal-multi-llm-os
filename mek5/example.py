"""
MEK-5: Failure as First-Class Output - Usage Example

Demonstrates failure as composable, explicit, and truthful.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from failure_primitives import (
    Phase,
    FailureType,
    Invariant,
    create_failure_event,
    create_failure_composition,
    create_failure_result,
)
from failure_guard import FailureGuard, get_failure_guard


class MockGuard:
    """
    Mock MEK Guard for demonstration.

    In production, this would be SnapshotAuthorityGuard from MEK-3.
    """

    def __init__(self):
        self.grants = {
            "user123": ["file_read", "file_write"],
        }

    def execute(self, capability_name: str, context: dict) -> dict:
        """
        Mock execute method.

        Simulates various failure types.
        """
        principal_id = context.get("principal_id")

        if principal_id not in self.grants:
            return {
                "is_success": False,
                "non_action": {
                    "reason": "UNKNOWN_PRINCIPAL",
                    "details": {"principal_id": principal_id},
                    "timestamp": 1234567890,
                },
            }

        if capability_name not in self.grants[principal_id]:
            return {
                "is_success": False,
                "non_action": {
                    "reason": "NO_GRANT",
                    "details": {
                        "capability": capability_name,
                        "principal_id": principal_id,
                    },
                    "timestamp": 1234567890,
                },
            }

        return {
            "is_success": True,
            "data": {"result": "executed"},
            "snapshot_id": "snap123",
        }


def main():
    """
    Main demonstration.

    Shows failure as first-class output.
    """
    print("MEK-5: Failure as First-Class Output Demo\n")
    print("=" * 60)

    # Create mock Guard
    guard = MockGuard()

    # Create failure guard
    fail_guard = get_failure_guard(guard)

    # Test 1: Successful execution
    print("\nTest 1: Successful execution (no failure)")
    print("-" * 60)

    result1 = fail_guard.execute_with_failure_tracking(
        capability_name="file_read",
        context={
            "principal_id": "user123",
            "confidence": 0.9,
        },
    )

    if result1.get("is_success", False):
        print("Execution succeeded")
        print(f"Data: {result1.get('data')}")
    else:
        print("Execution failed")
        failure = result1.get("failure")
        print(f"Failure Type: {failure.failure_type}")
        print(f"Triggering Condition: {failure.triggering_condition}")

    print(f"Has failures: {fail_guard.has_failures()}")

    # Clear for next test
    fail_guard.clear_failures()

    # Test 2: Unknown principal
    print("\nTest 2: Unknown principal (creates failure)")
    print("-" * 60)

    result2 = fail_guard.execute_with_failure_tracking(
        capability_name="file_read",
        context={
            "principal_id": "attacker999",
            "confidence": 0.9,
        },
    )

    if result2.get("is_success", False):
        print("Execution succeeded")
    else:
        print("Execution failed")
        failure = result2.get("failure")
        print(f"Failure ID: {failure.failure_id}")
        print(f"Phase: {failure.phase}")
        print(f"Failure Type: {failure.failure_type}")
        print(f"Triggering Condition: {failure.triggering_condition}")
        print(f"Authority Context: {failure.authority_context}")
        print(f"Timestamp: {failure.timestamp}")

    print(f"Has failures: {fail_guard.has_failures()}")

    # Get failure composition
    if fail_guard.has_failures():
        composition = fail_guard.get_failure_composition()
        print(f"\nFailure Composition:")
        print(f"  Composition ID: {composition.composition_id}")
        print(f"  Failures: {len(composition.failures)}")
        for i, fail in enumerate(composition.failures):
            print(f"    {i+1}. {fail.failure_type} at {fail.timestamp}")

    # Clear for next test
    fail_guard.clear_failures()

    # Test 3: Multiple failures
    print("\nTest 3: Multiple failures (composition)")
    print("-" * 60)

    # Step 1: Success
    result3a = fail_guard.execute_with_failure_tracking(
        capability_name="file_read",
        context={
            "principal_id": "user123",
            "confidence": 0.9,
            "step_id": "step1",
        },
        step_id="step1",
    )

    print(f"Step 1: {'SUCCESS' if result3a.get('is_success') else 'FAILURE'}")

    # Step 2: Failure
    result3b = fail_guard.execute_with_failure_tracking(
        capability_name="system_delete",
        context={
            "principal_id": "user123",
            "confidence": 0.9,
            "step_id": "step2",
        },
        step_id="step2",
    )

    print(f"Step 2: {'SUCCESS' if result3b.get('is_success') else 'FAILURE'}")

    print(f"\nFailure Composition:")
    if fail_guard.has_failures():
        composition = fail_guard.get_failure_composition()
        print(f"  Composition ID: {composition.composition_id}")
        print(f"  Total Failures: {len(composition.failures)}")

        for i, fail in enumerate(composition.failures):
            print(f"\n  Failure {i+1}:")
            print(f"    ID: {fail.failure_id}")
            print(f"    Phase: {fail.phase}")
            print(f"    Type: {fail.failure_type}")
            print(f"    Step: {fail.step_id}")
            print(f"    Condition: {fail.triggering_condition}")
            print(f"    Timestamp: {fail.timestamp}")

    # Test 4: Get failure result
    print("\n" + "=" * 60)
    print("Test 4: Failure Result")
    print("-" * 60)

    if fail_guard.has_failures():
        failure_result = fail_guard.get_failure_result()
        print(f"Composition ID: {failure_result.composition_id}")
        print(f"Terminal: {failure_result.terminal}")
        print(f"Failures: {len(failure_result.failures)}")

        print("\nNote: Failure result has NO success metadata")
        print("  - No 'data' field")
        print("  - No 'output' field")
        print("  - No 'final_result' field")
        print("  - Only 'failures' and 'terminal'")

    print("\n" + "=" * 60)
    print("Demo complete.\n")


def demonstrate_failure_immutability():
    """
    Demonstrate that failures are immutable.
    """
    print("\nDemonstrating Failure Immutability\n")
    print("=" * 60)

    failure = create_failure_event(
        failure_id="fail123",
        phase=Phase.MEK_3,
        failure_type=FailureType.MISSING_CONFIDENCE,
        triggering_condition="Confidence not provided",
    )

    print("\nFailure Event:")
    print(f"  ID: {failure.failure_id}")
    print(f"  Phase: {failure.phase}")
    print(f"  Type: {failure.failure_type}")
    print(f"  Condition: {failure.triggering_condition}")
    print(f"  Timestamp: {failure.timestamp}")

    print("\nAttempting to modify failure...")
    try:
        failure.failure_type = FailureType.INVALID_CONFIDENCE  # type: ignore
        print("  Modification succeeded (should not happen)")
    except Exception as e:
        print(f"  Modification failed (expected): {type(e).__name__}")

    print("\nFailure is immutable - cannot be changed after creation.")

    print("=" * 60)


def demonstrate_failure_composition():
    """
    Demonstrate failure composition rules.
    """
    print("\nDemonstrating Failure Composition Rules\n")
    print("=" * 60)

    # Create multiple failures
    failure1 = create_failure_event(
        failure_id="fail1",
        phase=Phase.MEK_3,
        failure_type=FailureType.MISSING_CONFIDENCE,
        triggering_condition="Confidence missing",
        timestamp=1000,
    )

    failure2 = create_failure_event(
        failure_id="fail2",
        phase=Phase.MEK_3,
        failure_type=FailureType.UNKNOWN_PRINCIPAL,
        triggering_condition="Unknown principal",
        timestamp=2000,
    )

    failure3 = create_failure_event(
        failure_id="fail3",
        phase=Phase.MEK_3,
        failure_type=FailureType.MISSING_GRANT,
        triggering_condition="No grant",
        timestamp=3000,
    )

    # Create composition
    composition = create_failure_composition(
        composition_id="comp_failures",
        failures=[failure1, failure2, failure3],
    )

    print("\nFailure Composition Rules:")
    print("  1. Preserves order of occurrence")
    print("  2. No deduplication")
    print("  3. No summarization")
    print("  4. No 'root cause' inference")
    print("  5. No severity ranking")
    print("  6. No collapsing")

    print(f"\nComposition contains {len(composition.failures)} failures:")
    for i, fail in enumerate(composition.failures):
        print(f"  {i+1}. {fail.failure_type} at {fail.timestamp}")

    print("\nNo root cause field:", not hasattr(composition, "root_cause"))
    print("No severity field:", not hasattr(composition, "severity"))
    print("No ranking field:", not hasattr(composition, "ranking"))

    print("\n" + "=" * 60)


def demonstrate_failure_types():
    """
    Demonstrate available failure types.
    """
    print("\nDemonstrating Failure Types\n")
    print("=" * 60)

    print("\nContext Failures:")
    print("  - MISSING_CONTEXT")
    print("  - INVALID_CONTEXT")
    print("  - CONTEXT_IMMUTABILITY_VIOLATION")

    print("\nIntent Failures:")
    print("  - MISSING_INTENT")
    print("  - INVALID_INTENT")
    print("  - INTENT_INFERENCE_ATTEMPT")

    print("\nConfidence Failures:")
    print("  - MISSING_CONFIDENCE")
    print("  - INVALID_CONFIDENCE")
    print("  - CONFIDENCE_THRESHOLD_EXCEEDED")

    print("\nPrincipal Failures:")
    print("  - MISSING_PRINCIPAL")
    print("  - UNKNOWN_PRINCIPAL")

    print("\nGrant Failures:")
    print("  - MISSING_GRANT")
    print("  - EXPIRED_GRANT")
    print("  - REVOKED_GRANT")
    print("  - EXHAUSTED_GRANT")
    print("  - INVALID_GRANT_SCOPE")

    print("\nCapability Failures:")
    print("  - UNKNOWN_CAPABILITY")
    print("  - CAPABILITY_SELF_INVOCATION")

    print("\nAuthority Failures:")
    print("  - UNIFIED_EXECUTION_AUTHORITY_VIOLATION")
    print("  - DIRECT_EXECUTION_ATTEMPT")

    print("\nFriction Failures:")
    print("  - FRICTION_VIOLATION")
    print("  - CONSEQUENCE_LEVEL_MISMATCH")

    print("\nSnapshot Failures:")
    print("  - SNAPSHOT_HASH_MISMATCH")
    print("  - SNAPSHOT_REUSE_ATTEMPT")
    print("  - TOCTOU_VIOLATION")

    print("\nComposition Failures:")
    print("  - COMPOSITION_STEP_FAILURE")
    print("  - COMPOSITION_ORDER_VIOLATION")

    print("\nExecution Failures:")
    print("  - EXECUTION_ERROR")
    print("  - GUARD_REFUSAL")

    print("\n" + "=" * 60)
    print("Note: FailureType enum is CLOSED - no new types allowed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
    demonstrate_failure_immutability()
    demonstrate_failure_composition()
    demonstrate_failure_types()
