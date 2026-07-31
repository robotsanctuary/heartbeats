"""
test_extraction_accuracy.py

Runs a small, hand-verified "golden set" of sample captions through
ai_extractor.py and checks the output against known-correct answers.

This is NOT testing whether the extractor is perfect (it never will be
on messy human text) -- it's testing whether it's still performing at
the level it was performing when you last checked. Run this:

  - Whenever you touch the extraction prompt or schema
  - On a schedule (weekly is reasonable) so a silent model update on
    OpenAI's end gets caught before it erodes your live data
  - Whenever confidence trends in accuracy_report.py look off

Usage:
    python test_extraction_accuracy.py

Exit code is non-zero if accuracy drops below ACCURACY_FLOOR, so this
can be wired into a scheduled job / CI check that emails/Slacks you on
failure.
"""

import json
import sys
from pathlib import Path

from ai_extractor import extract_pet_info

GOLDEN_SET_PATH = Path(__file__).parent / "golden_dataset.json"
ACCURACY_FLOOR = 0.85  # fail the run if accuracy drops below this


def check_case(case: dict, actual: dict) -> tuple[bool, list[str]]:
    """Compare actual extraction against the expected fields for one case."""
    expected = case["expected"]
    problems = []

    if "pet_id" in expected and actual.get("pet_id") != expected["pet_id"]:
        problems.append(f"pet_id: expected {expected['pet_id']!r}, got {actual.get('pet_id')!r}")

    if "shelter_name" in expected and expected["shelter_name"] is not None:
        if not actual.get("shelter_name") or expected["shelter_name"].lower() not in actual["shelter_name"].lower():
            problems.append(f"shelter_name: expected to contain {expected['shelter_name']!r}, got {actual.get('shelter_name')!r}")

    if "animal_name" in expected and expected["animal_name"] is not None:
        if not actual.get("animal_name") or expected["animal_name"].lower() not in actual["animal_name"].lower():
            problems.append(f"animal_name: expected to contain {expected['animal_name']!r}, got {actual.get('animal_name')!r}")

    if "deadline_not_null" in expected:
        is_null = actual.get("deadline") is None
        should_be_null = not expected["deadline_not_null"]
        if is_null != should_be_null:
            problems.append(f"deadline: expected {'null' if should_be_null else 'non-null'}, got {actual.get('deadline')!r}")

    return (len(problems) == 0, problems)


def run_regression_suite() -> float:
    golden_cases = json.loads(GOLDEN_SET_PATH.read_text())

    passed = 0
    print(f"Running {len(golden_cases)} golden-set extraction checks...\n")

    for case in golden_cases:
        actual = extract_pet_info(case["raw_text"])
        ok, problems = check_case(case, actual)

        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['id']}")
        if not ok:
            for p in problems:
                print(f"    - {p}")
        else:
            passed += 1

    accuracy = passed / len(golden_cases)
    print(f"\nAccuracy: {passed}/{len(golden_cases)} ({accuracy:.0%})")

    return accuracy


if __name__ == "__main__":
    accuracy = run_regression_suite()

    if accuracy < ACCURACY_FLOOR:
        print(f"\n⚠️  Accuracy {accuracy:.0%} is below the {ACCURACY_FLOOR:.0%} floor. "
              f"Check the prompt in ai_extractor.py and/or re-verify the golden set.")
        sys.exit(1)

    print(f"\n✅ Accuracy {accuracy:.0%} meets the {ACCURACY_FLOOR:.0%} floor.")
    sys.exit(0)
