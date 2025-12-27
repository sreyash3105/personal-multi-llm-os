"""
MEK-4: Composition Without Power - Usage Example

Demonstrates mechanical composition without emergent authority.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from composition_primitives import (
    Step,
    Composition,
    FailurePolicy,
    create_step,
    create_composition,
)
from composition_guard import CompositionGuard, get_composition_guard


class MockGuard:
    """
    Mock MEK Guard for demonstration.

    In production, this would be SnapshotAuthorityGuard from MEK-3.
    """

    def __init__(self):
        self.grants = {
            "user123": ["file_read", "file_write", "code_execute"],
        }
        self.executed_count = 0

    def execute(self, capability_name: str, context: dict) -> dict:
        """
        Mock execute method.

        Checks if principal has grant for capability.
        Returns success or refusal.
        """
        self.executed_count += 1
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
            "data": {
                "result": f"Executed {capability_name}",
                "context": context,
            },
            "snapshot_id": f"snap_{context.get('step_id', 'unknown')}",
        }


def main():
    """
    Main demonstration.

    Shows mechanical composition without emergent authority.
    """
    print("MEK-4: Composition Without Power Demo\n")
    print("=" * 60)

    # Create mock Guard
    guard = MockGuard()

    # Create composition guard
    comp_guard = get_composition_guard(guard)

    # Test 1: Successful composition
    print("\nTest 1: Successful composition (all steps authorized)")
    print("-" * 60)

    composition1 = create_composition(
        composition_id="comp_001",
        steps=[
            {
                "step_id": "read_config",
                "capability_name": "file_read",
                "context": {
                    "principal_id": "user123",
                    "confidence": 0.9,
                    "step_id": "read_config",
                    "path": "/etc/config.txt",
                },
                "order": 0,
            },
            {
                "step_id": "write_backup",
                "capability_name": "file_write",
                "context": {
                    "principal_id": "user123",
                    "confidence": 0.9,
                    "step_id": "write_backup",
                    "path": "/tmp/config.bak",
                },
                "order": 1,
            },
            {
                "step_id": "run_code",
                "capability_name": "code_execute",
                "context": {
                    "principal_id": "user123",
                    "confidence": 0.8,
                    "step_id": "run_code",
                    "code": "print('hello')",
                },
                "order": 2,
            },
        ],
    )

    result1 = comp_guard.execute_composition(composition1)

    print(f"Composition ID: {result1.composition_id}")
    print(f"Success: {result1.is_success}")
    print(f"Steps executed: {len(result1.steps)}")

    for step_result in result1.steps:
        if step_result.is_success:
            print(f"  Step {step_result.order} ({step_result.step_id}): SUCCESS")
            print(f"    Snapshot: {step_result.snapshot_id}")
        else:
            print(f"  Step {step_result.order} ({step_result.step_id}): REFUSED")
            print(f"    Reason: {step_result.non_action.get('reason')}")

    if result1.is_success:
        print(f"Final result: {result1.final_data}")

    # Test 2: Composition with refusal
    print("\nTest 2: Composition with refusal (step 2 unauthorized)")
    print("-" * 60)

    composition2 = create_composition(
        composition_id="comp_002",
        steps=[
            {
                "step_id": "read_file",
                "capability_name": "file_read",
                "context": {
                    "principal_id": "user123",
                    "confidence": 0.9,
                    "step_id": "read_file",
                    "path": "/tmp/data.txt",
                },
                "order": 0,
            },
            {
                "step_id": "delete_system",
                "capability_name": "system_delete",
                "context": {
                    "principal_id": "user123",
                    "confidence": 0.9,
                    "step_id": "delete_system",
                    "path": "/etc",
                },
                "order": 1,
            },
            {
                "step_id": "write_file",
                "capability_name": "file_write",
                "context": {
                    "principal_id": "user123",
                    "confidence": 0.9,
                    "step_id": "write_file",
                    "path": "/tmp/result.txt",
                },
                "order": 2,
            },
        ],
    )

    result2 = comp_guard.execute_composition(composition2)

    print(f"Composition ID: {result2.composition_id}")
    print(f"Success: {result2.is_success}")
    print(f"Halted at step: {result2.halted_at_step}")

    for step_result in result2.steps:
        if step_result.is_success:
            print(f"  Step {step_result.order} ({step_result.step_id}): SUCCESS")
        else:
            print(f"  Step {step_result.order} ({step_result.step_id}): REFUSED")
            print(f"    Reason: {step_result.non_action.get('reason')}")

    # Test 3: Composition with unknown principal
    print("\nTest 3: Composition with unknown principal")
    print("-" * 60)

    composition3 = create_composition(
        composition_id="comp_003",
        steps=[
            {
                "step_id": "read_secret",
                "capability_name": "file_read",
                "context": {
                    "principal_id": "attacker999",
                    "confidence": 0.9,
                    "step_id": "read_secret",
                    "path": "/etc/secret.txt",
                },
                "order": 0,
            },
        ],
    )

    result3 = comp_guard.execute_composition(composition3)

    print(f"Composition ID: {result3.composition_id}")
    print(f"Success: {result3.is_success}")
    print(f"Refusal reason: {result3.non_action.get('reason')}")

    print("\n" + "=" * 60)
    print("Demo complete.\n")


def demonstrate_independence():
    """
    Demonstrate that each step is independent.
    """
    print("\nDemonstrating Step Independence\n")
    print("=" * 60)

    guard = MockGuard()
    comp_guard = get_composition_guard(guard)

    composition = create_composition(
        composition_id="comp_independence",
        steps=[
            {
                "step_id": "step_a",
                "capability_name": "file_read",
                "context": {
                    "principal_id": "user123",
                    "confidence": 0.9,
                    "step_id": "step_a",
                    "path": "/file_a.txt",
                },
                "order": 0,
            },
            {
                "step_id": "step_b",
                "capability_name": "file_write",
                "context": {
                    "principal_id": "user123",
                    "confidence": 0.8,
                    "step_id": "step_b",
                    "path": "/file_b.txt",
                },
                "order": 1,
            },
        ],
    )

    result = comp_guard.execute_composition(composition)

    print("\nEach step has:")
    print("  - Independent Context")
    print("  - Independent Intent (capability)")
    print("  - Independent Snapshot")
    print("  - Independent Guard checks")

    print(f"\nSteps executed: {len(result.steps)}")
    print(f"Snapshots created:")
    for step_result in result.steps:
        print(f"  - {step_result.snapshot_id}")

    print("\nNo shared authority. No shared snapshot. No shared power.")

    print("=" * 60)


def demonstrate_strict_policy():
    """
    Demonstrate STRICT failure policy.
    """
    print("\nDemonstrating STRICT Failure Policy\n")
    print("=" * 60)

    guard = MockGuard()
    comp_guard = get_composition_guard(guard)

    # Step 2 will refuse
    composition = create_composition(
        composition_id="comp_strict",
        steps=[
            {
                "step_id": "step_1",
                "capability_name": "file_read",
                "context": {
                    "principal_id": "user123",
                    "confidence": 0.9,
                    "step_id": "step_1",
                    "path": "/file1.txt",
                },
                "order": 0,
            },
            {
                "step_id": "step_2",
                "capability_name": "system_delete",
                "context": {
                    "principal_id": "user123",
                    "confidence": 0.9,
                    "step_id": "step_2",
                    "path": "/system",
                },
                "order": 1,
            },
            {
                "step_id": "step_3",
                "capability_name": "file_write",
                "context": {
                    "principal_id": "user123",
                    "confidence": 0.9,
                    "step_id": "step_3",
                    "path": "/file2.txt",
                },
                "order": 2,
            },
        ],
    )

    result = comp_guard.execute_composition(composition)

    print("\nSTRICT policy:")
    print("  - First refusal halts entire composition")
    print("  - No retries")
    print("  - No alternative policies")

    print(f"\nSteps executed: {len(result.steps)}")
    print(f"Total steps in composition: {len(composition.steps)}")
    print(f"Halted at: {result.halted_at_step}")

    print(f"\nStep results:")
    for i, step_result in enumerate(result.steps):
        status = "SUCCESS" if step_result.is_success else "REFUSED"
        print(f"  Step {i} ({step_result.step_id}): {status}")

    print("\nOnly steps before refusal were executed.")
    print("Steps after refusal were never reached.")

    print("=" * 60)


if __name__ == "__main__":
    main()
    demonstrate_independence()
    demonstrate_strict_policy()
