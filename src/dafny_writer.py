import json
import logging
from typing import Optional

import ollama

from .schema import RequirementSchema

logger = logging.getLogger(__name__)

DAFNY_SYSTEM_PROMPT = r"""\
You are an expert Dafny programmer and formal verification specialist.

Your task is to convert a structured JSON specification of a software function into complete, compilable, and verifiable Dafny code.

You MUST output ONLY raw Dafny code. No markdown fences, no explanations, no extra text before or after the code.

## Non-Negotiable Format Rules

1. **Always wrap the code in a module declaration.**
   - Use `Validators` for numeric/bool checks.
   - Use `StringUtils` for string operations.
   - Use `InputValidation` for generic validation.
   - Use `NetworkUtils` for network-related checks.

2. **Convert the schema's `function_name` from snake_case to PascalCase for the Dafny identifier.**
   - Examples: `is_valid_age` -> `IsValidAge`, `is_strong_password` -> `IsStrongPassword`, `is_valid_http_status` -> `IsValidHttpStatus`.

3. **Always use `method` for boolean validator methods with preconditions/postconditions.**
   - Signature pattern: `method <PascalCaseName>(<params>) returns (result: bool)`
   - The return value MUST be named `result` and be of type `bool`.

4. **Always include both `requires` and `ensures` clauses.**
   - `requires` captures input restrictions (from assumptions and negative constraints).
   - `ensures` captures the exact success condition as `result == (<boolean expression>)`.

5. **The method body MUST be a direct boolean assignment matching the ensures clause.**
   - Pattern: `result := <same boolean expression as ensures>;`
   - Do NOT use loops, conditionals, or helper methods unless the schema explicitly requires them.

## Translation Cheat Sheet

| JSON type | Dafny type |
|-----------|------------|
| "string"  | `string`   |
| "int"     | `int`      |
| "bool"    | `bool`     |

| Concept | Dafny pattern |
|---------|---------------|
| String length | `\|s\|` |
| Digit check | `c in '0'..'9'` |
| Upper/lower alpha | `c in 'A'..'Z'` or `c in 'a'..'z'` |
| Exists digit in string | `exists c :: c in s && c in '0'..'9'` |
| All chars satisfy | `forall c :: c in s ==> <property>` |
| Exact length | `\|s\| == <n>` |
| Range check | `x >= <low> && x <= <high>` |

## Correctness Requirements

1. **Faithful translation:** Do not add or remove behavior from the schema.
2. **No markdown:** Output raw Dafny only. No fences, no ```dafny, no explanations.
3. **Syntactically valid:** Balanced braces, proper semicolons, correct Dafny syntax.
4. **Verifiable:** The ensures clause must exactly match the body expression so Dafny can verify automatically.

## Example

Input schema (JSON):
{
  "function_name": "is_valid_age",
  "purpose": "Check whether a given integer represents a valid human age.",
  "inputs": [{"name": "age", "type": "int"}],
  "output": {"type": "bool"},
  "observations": ["A valid age is at least 0.", "A valid age is at most 150."],
  "constraints": [
    {"condition": "age < 0", "consequence": "output is false"},
    {"condition": "age > 150", "consequence": "output is false"},
    {"condition": "age >= 0 AND age <= 150", "consequence": "output is true"}
  ],
  "assumptions": ["Input is a 32-bit integer."],
  "edge_cases": [
    {"input": "-1", "expected_output": "false", "reason": "One below lower bound"},
    {"input": "0", "expected_output": "true", "reason": "Exact lower bound"}
  ],
  "success_condition": "Returns true if and only if age >= 0 AND age <= 150.",
  "closed_world": {"confirmed": true, "unresolved_ambiguities": []}
}

Expected Dafny output:
module Validators {
  method IsValidAge(age: int) returns (result: bool)
    requires age >= 0 && age <= 150
    ensures result == (age >= 0 && age <= 150)
  {
    result := age >= 0 && age <= 150;
  }
}

Notice:
- Module name `Validators` (numeric/bool checks).
- Method name `IsValidAge` (PascalCase from `is_valid_age`).
- Return value `result: bool`.
- `requires` from input constraints/assumptions.
- `ensures` from success_condition.
- Body is direct boolean assignment matching ensures exactly.
"""


def _convert_name(name: str) -> str:
    """Convert snake_case to PascalCase for Dafny identifiers."""
    return "".join(part.capitalize() for part in name.split("_"))


def _dafny_type(json_type: str) -> str:
    mapping = {
        "string": "string",
        "int": "int",
        "bool": "bool",
        "integer": "int",
        "boolean": "bool",
    }
    return mapping.get(json_type.lower(), json_type)


def schema_to_dafny_prompt(schema: RequirementSchema) -> str:
    """Serialize the RequirementSchema into a JSON string for the LLM prompt."""
    return json.dumps(schema.model_dump(), indent=2)


def generate_dafny(
    schema: RequirementSchema,
    model: str = "llama3",
    host: Optional[str] = None,
) -> str:
    """
    Send a RequirementSchema to an Ollama LLM and return valid Dafny code.

    Args:
        schema: The parsed requirement specification.
        model: Ollama model tag (default: "llama3").
        host: Optional Ollama host URL.

    Returns:
        str: Raw Dafny source code.

    Raises:
        RuntimeError: If the LLM response is empty or malformed.
    """
    client_kwargs: dict = {}
    if host:
        client_kwargs["host"] = host

    user_prompt = (
        "Convert the following structured requirement specification into valid, "
        "verifiable Dafny code.\\n\\n"
        f"```json\\n{schema_to_dafny_prompt(schema)}\\n```\\n\\n"
        "Remember: output ONLY raw Dafny code. No markdown fences. No explanations."
    )

    logger.debug("Sending schema to Ollama model=%s for Dafny generation", model)

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": DAFNY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        **client_kwargs,
    )

    content = response["message"]["content"].strip()
    logger.debug("Raw Dafny response:\\n%s", content)

    if not content:
        raise RuntimeError("Ollama returned an empty response for Dafny generation.")

    return content
