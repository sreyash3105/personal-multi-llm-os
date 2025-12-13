import sys
import time
import logging
from pathlib import Path

# Ensure backend can be imported
sys.path.append(str(Path(__file__).parent))

from backend.modules.code.pipeline import run_coder, run_reviewer
from backend.core.config import CODER_MODEL_NAME, REVIEWER_MODEL_NAME

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

def test_pipeline():
    print(f"\n🏭 TESTING CODE PIPELINE...")
    print(f"   Coder Model:    {CODER_MODEL_NAME}")
    print(f"   Reviewer Model: {REVIEWER_MODEL_NAME}\n")

    prompt = "Write a Python function that generates the Fibonacci sequence up to N terms."
    print(f"📝 Prompt: '{prompt}'")

    # --- STEP 1: CODER ---
    print("\n[1/2] Running Coder (Drafting)...")
    start = time.time()
    try:
        draft_code = run_coder(prompt)
        duration = time.time() - start
        
        if not draft_code or "failed" in draft_code.lower() and len(draft_code) < 100:
            print(f"❌ Coder Failed: {draft_code}")
            return

        print(f"✅ Coder Finished ({duration:.2f}s)")
        print("--- DRAFT OUTPUT (Snippet) ---")
        print('\n'.join(draft_code.split('\n')[:5]) + "\n...[truncated]...")
        print("------------------------------")

    except Exception as e:
        print(f"❌ Coder Crashed: {e}")
        return

    # --- STEP 2: REVIEWER ---
    print(f"\n[2/2] Running Reviewer (Refining)...")
    start = time.time()
    try:
        final_code = run_reviewer(prompt, draft_code)
        duration = time.time() - start

        if not final_code:
            print("❌ Reviewer returned empty.")
            return

        print(f"✅ Reviewer Finished ({duration:.2f}s)")
        print("--- FINAL OUTPUT (Snippet) ---")
        print('\n'.join(final_code.split('\n')[:5]) + "\n...[truncated]...")
        print("------------------------------")

    except Exception as e:
        print(f"❌ Reviewer Crashed: {e}")
        return

    print("\n✨ PIPELINE STATUS: OPERATIONAL")

if __name__ == "__main__":
    test_pipeline()