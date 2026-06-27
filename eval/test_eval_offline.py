import json
import logging
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.schema import RequirementSchema, InputField, OutputField, Constraint, EdgeCase, ClosedWorld
from src.dafny_verifier import verify_dafny
from eval.run_eval import EvalResult, compute_summary, generate_report

logging.basicConfig(level=logging.INFO)



def build_mock_results() -> list:
    r1 = EvalResult(
        id="R01",
        nl_requirement="Test age requirement",
        predicted_schema={
            "function_name": "is_valid_age",
            "purpose": "Check age.",
            "inputs": [{"name": "age", "type": "int", "description": "Age"}],
            "output": {"type": "bool", "description": "Valid?"},
            "observations": ["Age must be >= 0", "Age must be <= 150"],
            "constraints": [
                {"condition": "age < 0", "consequence": "false"},
                {"condition": "age > 150", "consequence": "false"},
                {"condition": "age >= 0 AND age <= 150", "consequence": "true"},
            ],
            "assumptions": ["32-bit int"],
            "edge_cases": [
                {"input": "-1", "expected_output": "false", "reason": "Below"},
                {"input": "0", "expected_output": "true", "reason": "Boundary"},
            ],
            "success_condition": "age >= 0 AND age <= 150",
            "closed_world": {"confirmed": True, "unresolved_ambiguities": []},
            "backdoor_note": None,
        },
        reference_schema={
            "function_name": "is_valid_age",
            "purpose": "Check whether a given integer represents a valid human age.",
            "inputs": [{"name": "age", "type": "int", "description": "The age value to validate."}],
            "output": {"type": "bool", "description": "True if the age is between 0 and 150 inclusive, false otherwise."},
            "observations": ["A valid age is at least 0.", "A valid age is at most 150."],
            "constraints": [
                {"condition": "age < 0", "consequence": "output is false"},
                {"condition": "age > 150", "consequence": "output is false"},
                {"condition": "age >= 0 AND age <= 150", "consequence": "output is true"},
            ],
            "assumptions": ["Input is a 32-bit integer.", "No fractional ages are considered."],
            "edge_cases": [
                {"input": "-1", "expected_output": "false", "reason": "One below lower bound"},
                {"input": "0", "expected_output": "true", "reason": "Exact lower bound"},
            ],
            "success_condition": "Returns true if and only if age >= 0 AND age <= 150.",
            "closed_world": {"confirmed": True, "unresolved_ambiguities": []},
            "backdoor_note": None,
        },
        schema_judge_result={
            "score": 0.9,
            "function_name_match": True,
            "purpose_match": True,
            "inputs_match": True,
            "output_match": True,
            "observations_match": True,
            "constraints_match": True,
            "assumptions_match": False,
            "edge_cases_match": True,
            "success_condition_match": True,
            "closed_world_match": True,
            "differences": ["Missing 'No fractional ages are considered' assumption"],
            "reasoning": "Predicted schema is very close but omits one assumption.",
        },
        predicted_dafny="module Validators { method IsValidAge(age: int) returns (result: bool) requires age >= 0 && age <= 150 ensures result == (age >= 0 && age <= 150) { result := age >= 0 && age <= 150; } }",
        reference_dafny="module Validators { method IsValidAge(age: int) returns (result: bool) requires age >= 0 && age <= 150 ensures result == (age >= 0 && age <= 150) { result := age >= 0 && age <= 150; } }",
        dafny_judge_result={
            "is_correct": True,
            "semantic_equivalence_score": 1.0,
            "matches_specification": True,
            "compiles_likely": True,
            "would_verify": True,
            "differences": [],
            "missing_elements": [],
            "extra_elements": [],
            "reasoning": "Identical implementations.",
        },
        dafny_verification={
            "is_valid": True,
            "errors": [],
            "verification_passed": True,
            "dafny_output": "Dafny program verifies successfully",
        },
    )

    r2 = EvalResult(
        id="R02",
        nl_requirement="Test port requirement",
        predicted_schema={
            "function_name": "is_valid_port",
            "purpose": "Check port.",
            "inputs": [{"name": "port", "type": "int", "description": "Port"}],
            "output": {"type": "bool", "description": "Valid?"},
            "observations": ["Port must be >= 1"],
            "constraints": [
                {"condition": "port < 1", "consequence": "false"},
                {"condition": "port > 65535", "consequence": "false"},
                {"condition": "port >= 1 AND port <= 65535", "consequence": "true"},
            ],
            "assumptions": ["32-bit int"],
            "edge_cases": [
                {"input": "0", "expected_output": "false", "reason": "Reserved"},
                {"input": "1", "expected_output": "true", "reason": "Lower"},
            ],
            "success_condition": "port >= 1 AND port <= 65535",
            "closed_world": {"confirmed": True, "unresolved_ambiguities": []},
            "backdoor_note": None,
        },
        reference_schema={},
        predicted_dafny="module Validators { method IsValidPort(port: int) returns (result: bool) requires port >= 1 && port <= 65535 ensures result == (port >= 1 && port <= 65535) { result := port >= 1 && port <= 65535; } }",
        reference_dafny="module Validators { method IsValidPort(port: int) returns (result: bool) requires port >= 1 && port <= 65535 ensures result == (port >= 1 && port <= 65535) { result := port >= 1 && port <= 65535; } }",
        schema_judge_result={
            "score": 0.7,
            "function_name_match": True,
            "purpose_match": False,
            "inputs_match": True,
            "output_match": True,
            "observations_match": False,
            "constraints_match": True,
            "assumptions_match": True,
            "edge_cases_match": True,
            "success_condition_match": True,
            "closed_world_match": True,
            "differences": ["Purpose too brief", "Missing some observations"],
            "reasoning": "Core logic correct but details sparse.",
        },
        dafny_judge_result={
            "is_correct": True,
            "semantic_equivalence_score": 1.0,
            "matches_specification": True,
            "compiles_likely": True,
            "would_verify": True,
            "differences": [],
            "missing_elements": [],
            "extra_elements": [],
            "reasoning": "Identical implementations.",
        },
        dafny_verification={
            "is_valid": True,
            "errors": [],
            "verification_passed": True,
            "dafny_output": "Dafny program verifies successfully",
        },
    )

    r3 = EvalResult(
        id="R03",
        nl_requirement="Test broken requirement",
        error="Simulated pipeline failure",
    )

    return [r1, r2, r3]


def main() -> None:
    results = build_mock_results()

    # Test compute_summary
    summary = compute_summary(results)
    print("Summary:", json.dumps(summary, indent=2))

    assert summary["total"] == 3
    assert summary["errors"] == 1
    assert summary["schema"]["avg_score"] > 0.0
    assert summary["dafny"]["correct_count"] == 2
    assert summary["dafny"]["correct_rate"] == 2 / 3

    # Test report generation
    report = generate_report(results, summary)
    assert "# Evaluation Report" in report
    assert "R01" in report
    assert "R02" in report
    assert "R03" in report
    assert "Pipeline errors: 1" in report

    # Save report
    with open("eval\report.md", "w", encoding="utf-8") as f:
        f.write(report)

    print("\nAll offline eval tests passed.")


if __name__ == "__main__":
    main()
