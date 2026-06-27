import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from src.schema import RequirementSchema, InputField, OutputField, Constraint, EdgeCase, ClosedWorld
from src.dafny_writer import schema_to_dafny_prompt, _convert_name
from src.dafny_verifier import verify_dafny

logging.basicConfig(level=logging.INFO)



def load_requirements(limit=3):
    with open("eval/ground_truth.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["requirements"][:limit]


SIMULATED_LLM_DAFNY = {
    "is_valid_age": "module Validators {\n  method IsValidAge(age: int) returns (result: bool)\n    requires age >= 0 && age <= 150\n    ensures result == (age >= 0 && age <= 150)\n  {\n    result := age >= 0 && age <= 150;\n  }\n}",
    "is_valid_http_status": "module Validators {\n  method IsValidHttpStatus(code: int) returns (result: bool)\n    requires code >= 100 && code <= 599\n    ensures result == (code >= 100 && code <= 599)\n  {\n    result := code >= 100 && code <= 599;\n  }\n}",
    "is_valid_percentage": "module Validators {\n  method IsValidPercentage(value: int) returns (result: bool)\n    requires value >= 0 && value <= 100\n    ensures result == (value >= 0 && value <= 100)\n  {\n    result := value >= 0 && value <= 100;\n  }\n}",
    "is_strong_password": "module Validators {\n  method IsStrongPassword(password: string) returns (result: bool)\n    requires |password| >= 8\n    ensures result == (|password| >= 8 && exists c :: c in password && c in '0'..'9')\n  {\n    result := |password| >= 8 && exists c :: c in password && c in '0'..'9';\n  }\n}",
    "is_alpha": "module StringUtils {\n  method IsAlpha(s: string) returns (result: bool)\n    requires |s| >= 1\n    ensures result == (|s| >= 1 && forall c :: c in s ==> c in 'A'..'Z' || c in 'a'..'z')\n  {\n    result := |s| >= 1 && forall c :: c in s ==> c in 'A'..'Z' || c in 'a'..'z';\n  }\n}",
    "is_alphanumeric": "module StringUtils {\n  method IsAlphanumeric(s: string) returns (result: bool)\n    requires |s| >= 1\n    ensures result == (|s| >= 1 && forall c :: c in s ==> c in 'A'..'Z' || c in 'a'..'z' || c in '0'..'9')\n  {\n    result := |s| >= 1 && forall c :: c in s ==> c in 'A'..'Z' || c in 'a'..'z' || c in '0'..'9';\n  }\n}",
    "is_valid_hex_color": "module StringUtils {\n  method IsValidHexColor(color: string) returns (result: bool)\n    requires |color| == 7\n    ensures result == (|color| == 7 && color[0] == '#' && forall i :: 1 <= i < 7 ==> color[i] in '0'..'9' || color[i] in 'A'..'F' || color[i] in 'a'..'f')\n  {\n    result := |color| == 7 && color[0] == '#' && forall i :: 1 <= i < 7 ==> color[i] in '0'..'9' || color[i] in 'A'..'F' || color[i] in 'a'..'f';\n  }\n}",
}


OPTIMIZED_PROMPT_NOTE = """
Observed improvements needed:
- Always wrap in a module (choose name by category: Validators, StringUtils, etc.).
- Use PascalCase method/function names derived from function_name.
- Always include `returns (result: bool)` for bool outputs.
- Map constraints to `requires` (input restrictions) and `ensures` (output behavior).
- For string length: use `|s|`.
- For digit/character checks: use `c in set` or `forall c :: c in s ==> ...`.
- Keep body as direct boolean assignment; do not write loops unless necessary.
- Do NOT omit postconditions; the judge and verifier rely on them.
"""


def main() -> None:
    reqs = load_requirements(limit=3)

    print("=== Simulated Pipeline + Verification ===\n")

    scores = []
    for req in reqs:
        name = req["schema"]["function_name"]
        print(f"--- {req['id']}: {name} ---")

        pascal = _convert_name(name)

        raw = SIMULATED_LLM_DAFNY.get(name)
        if raw is None:
            print(f"[SKIP] No simulated Dafny for {name}\n")
            continue

        print("Generated Dafny:\n" + raw + "\n")

        v = verify_dafny(raw)
        print("Verification -> is_valid=%s, passed=%s" % (v.is_valid, v.verification_passed))
        if v.errors:
            print("Errors:")
            for e in v.errors:
                print("  * " + e)
        print()
        scores.append((name, v.is_valid, v.verification_passed))

    print("=== Optimized prompt guidance ===")
    print(OPTIMIZED_PROMPT_NOTE)

    print("\n=== Summary ===")
    for name, valid, passed in scores:
        print(f"  {name}: valid={valid}, verification_passed={passed}")


if __name__ == "__main__":
    main()
