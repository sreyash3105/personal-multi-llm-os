import sys
import json
import logging

# Ensure we can import from backend
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# Import the Planner
from backend.modules.planner.planner import Planner

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

def test_brain():
    print("\n[BRAIN] WAKING UP PLANNER BRAIN...\n")
    
    planner = Planner.shared()
    
    # Test Case 1: Complex Multi-step Instruction
    prompt = "Check if 'notes.txt' exists, and if it does, read it and summarize it."
    
    print(f"[PROMPT] User Prompt: '{prompt}'")
    print("Thinking...")
    
    try:
        # Ask the Planner to think
        plan = planner.plan_request(
            user_input=prompt,
            context={"profile_id": "test_user", "source": "cli_test"}
        )
        
        # Output the result
        print("\n[PLAN GENERATED]")
        print(json.dumps(plan, indent=2))
        
        # Validation Checks
        if plan.get("intent") == "automation" or plan.get("intent") == "file_op":
            print("\n[OK] Intent Detection: PASS (Correctly identified automation/file op)")
        else:
            print(f"\n[WARNING] Intent Detection: WARNING (Got '{plan.get('intent')}', expected automation)")
            
        if isinstance(plan.get("risk_hint"), int):
            print("[OK] Risk Scoring: PASS (Valid integer)")
        else:
            print("[FAIL] Risk Scoring: FAIL (Not an integer)")

    except Exception as e:
        print(f"\n[FAIL] PLANNER CRASHED: {e}")

if __name__ == "__main__":
    test_brain()