#!/usr/bin/env python3
"""
Test cases for robust judge response parsing.
Run with: python test_judge_parsing.py
"""

import sys
import os
sys.path.append('backend')

from modules.code.pipeline import _parse_judge_response

def test_judge_parsing():
    """Test various edge cases for judge response parsing."""

    # Test cases: (input, should_pass, expected_result_or_error_type)
    test_cases = [
        # Valid cases
        ('{"confidence_score": 8, "conflict_score": 3, "judgement_summary": "Looks correct"}',
         True, {"confidence_score": 8.0, "conflict_score": 3.0, "judgement_summary": "Looks correct"}),

        ('Some text before {"confidence_score": 5, "conflict_score": 5, "judgement_summary": "OK"} and after',
         True, {"confidence_score": 5.0, "conflict_score": 5.0, "judgement_summary": "OK"}),

        # Edge case: string numbers (should convert)
        ('{"confidence_score": "7", "conflict_score": "2", "judgement_summary": "Good"}',
         True, {"confidence_score": 7.0, "conflict_score": 2.0, "judgement_summary": "Good"}),

        # Edge case: truncated summary
        ('{"confidence_score": 1, "conflict_score": 1, "judgement_summary": "' + 'x' * 2000 + '"}',
         True, {"confidence_score": 1.0, "conflict_score": 1.0, "judgement_summary": 'x' * 997 + "..."}),

        # Invalid cases
        ('No JSON here', False, ValueError),
        ('{"confidence_score": 11, "conflict_score": 1}', False, ValueError),  # Score too high
        ('{"confidence_score": 0, "conflict_score": 1}', False, ValueError),   # Score too low
        ('{"confidence_score": "not_a_number", "conflict_score": 1}', False, ValueError),
        ('{"invalid_key": 1}', False, ValueError),  # Missing required fields
        ('{"confidence_score": 1, "conflict_score": 1, "judgement_summary": 123}', False, ValueError),  # Wrong type
        ('[' + 'x' * 10001 + ']', False, ValueError),  # Too large
        ('', False, ValueError),  # Empty
    ]

    print("Testing judge response parsing...")
    passed = 0
    total = len(test_cases)

    for i, (input_str, should_pass, expected) in enumerate(test_cases, 1):
        try:
            result = _parse_judge_response(input_str)
            if should_pass:
                if result == expected:
                    print(f"[PASS] Test {i}: OK")
                    passed += 1
                else:
                    print(f"[FAIL] Test {i}: Expected {expected}, got {result}")
            else:
                print(f"[FAIL] Test {i}: Should have raised exception but got {result}")
        except Exception as e:
            if not should_pass and isinstance(e, expected):
                print(f"[PASS] Test {i}: Correctly raised {type(e).__name__}")
                passed += 1
            else:
                print(f"[FAIL] Test {i}: Unexpected {type(e).__name__}: {e}")

    print(f"\nResults: {passed}/{total} tests passed")
    return passed == total

if __name__ == "__main__":
    success = test_judge_parsing()
    sys.exit(0 if success else 1)