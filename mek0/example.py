"""
MEK-0 Example Usage

Demonstrates kernel primitives and invariant enforcement.
"""

from mek0.kernel import (
    Context, CapabilityContract, ConsequenceLevel,
    get_guard, create_success,
    get_observer_hub, Observer,
)


# Example Observer
class PrintObserver(Observer):
    def on_event(self, event_type: str, details: dict):
        print(f"[OBSERVER] {event_type}: {details}")


# Example Capability
def greet_user(context: Context) -> str:
    """Simple greeting capability."""
    user_id = context.fields.get("user_id", "guest")
    return f"Hello, {user_id}!"


def process_data(context: Context) -> dict:
    """Data processing capability."""
    data = context.fields.get("data", {})
    return {"processed": True, "item_count": len(data)}


def main():
    # Register observer
    observer = PrintObserver()
    get_observer_hub().register(observer)

    # Create guard
    guard = get_guard()

    # Register capabilities
    greet_cap = CapabilityContract(
        name="greet",
        consequence_level=ConsequenceLevel.LOW,
        required_context_fields=["user_id"],
        _execute_fn=greet_user,
    )

    process_cap = CapabilityContract(
        name="process",
        consequence_level=ConsequenceLevel.MEDIUM,
        required_context_fields=["data"],
        _execute_fn=process_data,
    )

    guard.register_capability(greet_cap)
    guard.register_capability(process_cap)

    # Example 1: Valid execution
    print("\n=== Example 1: Valid Execution ===")
    context = Context(
        context_id="example-1",
        confidence=0.9,
        intent="greet",
        fields={"user_id": "Alice"},
    )
    result = guard.execute("greet", context)
    if result.is_success():
        print(f"Success: {result.data}")
    else:
        print(f"Non-Action: {result.non_action}")

    # Example 2: HIGH consequence with friction
    print("\n=== Example 2: HIGH Consequence (10s friction) ===")
    high_cap = CapabilityContract(
        name="delete_database",
        consequence_level=ConsequenceLevel.HIGH,
        required_context_fields=["confirmation"],
        _execute_fn=lambda ctx: "Database deleted",
    )
    guard.register_capability(high_cap)

    import time
    start = time.time()
    context = Context(
        context_id="example-2",
        confidence=0.95,
        intent="delete_database",
        fields={"confirmation": True},
    )
    result = guard.execute("delete_database", context)
    elapsed = time.time() - start
    print(f"Execution completed in {elapsed:.1f}s (friction enforced)")
    if result.is_success():
        print(f"Success: {result.data}")

    # Example 3: Missing context field → Non-Action
    print("\n=== Example 3: Missing Context Field ===")
    context = Context(
        context_id="example-3",
        confidence=0.8,
        intent="process",
        fields={},  # Missing required "data" field
    )
    result = guard.execute("process", context)
    if result.is_success():
        print(f"Success: {result.data}")
    else:
        print(f"Non-Action (missing_context): {result.non_action}")

    # Example 4: Invalid confidence → Non-Action
    print("\n=== Example 4: Invalid Confidence ===")
    try:
        context = Context(
            context_id="example-4",
            confidence=1.5,  # Invalid (> 1.0)
            intent="greet",
            fields={"user_id": "Bob"},
        )
        result = guard.execute("greet", context)
        print(f"Result: {result}")
    except ValueError as e:
        print(f"Context creation rejected: {e}")

    # Example 5: Unknown capability → Non-Action
    print("\n=== Example 5: Unknown Capability ===")
    context = Context(
        context_id="example-5",
        confidence=0.9,
        intent="unknown_capability",
        fields={},
    )
    result = guard.execute("unknown_capability", context)
    if result.is_success():
        print(f"Success: {result.data}")
    else:
        print(f"Non-Action (refused_by_guard): {result.non_action}")

    # Clean up
    get_observer_hub().clear()


if __name__ == "__main__":
    main()
