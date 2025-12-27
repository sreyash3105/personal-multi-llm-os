import sys
import json
import logging
from pathlib import Path

# Ensure backend can be imported
sys.path.append(str(Path(__file__).parent.parent))

from backend.modules.code.pipeline import run_judge
from backend.core.config import JUDGE_MODEL_NAME

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

def test_judge():
    print(f"\n[JUDGE] WAKING UP JUDGE BRAIN (Model: {JUDGE_MODEL_NAME})...\n")

    # Mock Inputs: A common coding scenario
    user_prompt = "Write a Python function to calculate the factorial of a number."
    
    # 1. Draft code (simulating a quick Coder model - functional but bare)
    coder_draft = """
def factorial(n):
    if n == 0: return 1
    return n * factorial(n-1)
"""

    # 2. Reviewed code (simulating a Reviewer model - robust with error handling)
    reviewer_final = """
def factorial(n: int) -> int:
    '''Calculates factorial recursively.'''
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers.")
    if n == 0:
        return 1
    return n * factorial(n - 1)
"""

    print(f"[PROMPT] User Prompt: '{user_prompt}'")
    print("Thinking (comparing Draft vs Final)...")

    try:
        # Run the Judge
        result = run_judge(
            original_prompt=user_prompt,
            coder_output=coder_draft,
            reviewer_output=reviewer_final
        )

        # Output the raw JSON result
        print("\n[JUDGE VERDICT]")
        print(json.dumps(result, indent=2))

        # Verification Logic
        conf = result.get("confidence_score")
        conflict = result.get("conflict_score")

        if conf is not None and conflict is not None:
            print(f"\n[OK] Judge is active! (Confidence: {conf}/10, Conflict: {conflict}/10)")
            if conf > 8.0:
                print("   -> High confidence detected (Expected behavior for good code).")
        else:
            print("\n[WARNING] Judge returned None scores. The model might not be following JSON format.")

    except Exception as e:
        print(f"\n[FAIL] JUDGE FAILED: {e}")

if __name__ == "__main__":
    test_judge()