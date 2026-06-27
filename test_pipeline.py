import logging

from src.schema import RequirementSchema, InputField, OutputField, Constraint, EdgeCase, ClosedWorld
from src.dafny_writer import schema_to_dafny_prompt, _convert_name
from src.dafny_verifier import verify_dafny

logging.basicConfig(level=logging.INFO)


def build_fake_schema() -> RequirementSchema:
    return RequirementSchema(
        function_name="is_strong_password",
        purpose="Determine whether a given string qualifies as a strong password.",
        inputs=[
            InputField(name="password", type="string", description="The password string to be evaluated")
        ],
        output=OutputField(type="bool", description="True if the password is strong, false otherwise"),
        observations=[
            "A strong password must be at least 8 characters long",
            "A strong password must contain at least one digit (0-9)",
        ],
        constraints=[
            Constraint(condition="|password| < 8", consequence="output is false"),
            Constraint(condition="password contains no character in [0-9]", consequence="output is false"),
            Constraint(
                condition="|password| >= 8 AND password contains at least one character in [0-9]",
                consequence="output is true",
            ),
        ],
        assumptions=["Input is a non-null string", "Unicode characters count as single characters"],
        edge_cases=[
            EdgeCase(input='""', expected_output="false", reason="empty string fails length constraint"),
            EdgeCase(input='"1234567"', expected_output="false", reason="has digit but length is 7"),
            EdgeCase(input='"abcdefgh"', expected_output="false", reason="length is 8 but no digit"),
            EdgeCase(input='"abcdefg1"', expected_output="true", reason="exactly 8 characters with one digit"),
        ],
        success_condition=(
            "Returns true if and only if password length >= 8 AND "
            "password contains at least one character in 0-9"
        ),
        closed_world=ClosedWorld(
            confirmed=True,
            unresolved_ambiguities=[
                "Requirement does not specify whether spaces are allowed",
                "Requirement does not specify case sensitivity",
            ],
        ),
    )


def main() -> None:
    schema = build_fake_schema()

    print("=== Test 1: Prompt formatting ===")
    prompt = schema_to_dafny_prompt(schema)
    assert "is_strong_password" in prompt
    assert "bool" in prompt
    print("OK: schema serializes to JSON containing expected keys.")

    print("\n=== Test 2: Name conversion ===")
    assert _convert_name("is_strong_password") == "IsStrongPassword"
    print("OK: _convert_name('is_strong_password') == 'IsStrongPassword'")

    print("\n=== Test 3: Verifier with valid Dafny ===")
    valid_dafny = """\
module Validators {
  /// Determine whether a given string qualifies as a strong password.
  method IsStrongPassword(password: string) returns (result: bool)
    requires |password| >= 8
    ensures result == (|password| >= 8 && exists c :: c in password && c in '0'..'9')
  {
    result := |password| >= 8 && exists c :: c in password && c in '0'..'9';
  }
}
"""
    result = verify_dafny(valid_dafny)
    assert result.is_valid is True
    print(f"OK: valid_dafny -> is_valid={result.is_valid}, verification_passed={result.verification_passed}")

    print("\n=== Test 4: Verifier with invalid Dafny ===")
    invalid_dafny = """\
module Validators {
  method IsStrongPassword(password: string) returns (result: bool)
    requires |password| >= 8
    ensures result == (|password| >= 8 && exists c :: c in password && c in '0'..'9')
  {
    // missing closing brace
"""
    result = verify_dafny(invalid_dafny)
    assert result.is_valid is False
    assert result.errors
    print(f"OK: invalid_dafny -> is_valid={result.is_valid}, errors={result.errors}")

    print("\n=== All offline tests passed. ===")
    print("To run the full live pipeline, start Ollama and run:")
    print("  python test_pipeline_live.py")


if __name__ == "__main__":
    main()
