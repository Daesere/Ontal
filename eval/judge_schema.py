import json
import logging
from typing import Optional

import ollama

logger = logging.getLogger(__name__)

SCHEMA_JUDGE_SYSTEM_PROMPT = """\
You are an expert software requirements analyst evaluating how well a predicted structured schema matches a ground-truth schema, given the original natural-language requirement.

You will receive:
1. The original natural-language requirement.
2. The ground-truth schema (JSON).
3. The predicted schema (JSON).

Your task is to compare them semantically, not lexically. The predicted schema may use different wording but must capture the same meaning.

## Output Format

You MUST output ONLY a single JSON object. No markdown, no explanations outside the JSON.

```json
{
  "score": <float between 0.0 and 1.0>,
  "function_name_match": <bool>,
  "purpose_match": <bool>,
  "inputs_match": <bool>,
  "output_match": <bool>,
  "observations_match": <bool>,
  "constraints_match": <bool>,
  "assumptions_match": <bool>,
  "edge_cases_match": <bool>,
  "success_condition_match": <bool>,
  "closed_world_match": <bool>,
  "differences": ["<string>"],
  "reasoning": "<string>"
}
```

## Scoring Guidelines

- `1.0`: Predicted schema is semantically equivalent to ground truth. All required fields are present and correct. Minor wording differences are acceptable.
- `0.8-0.9`: Minor omissions or slight differences in wording, but all critical requirements are captured.
- `0.5-0.7`: Some important fields are missing or incorrect. Core idea is there but details differ.
- `0.1-0.4`: Major fields missing or incorrect. Significant differences in meaning.
- `0.0`: Completely wrong schema or no useful content.

## Field-specific guidance

- `function_name_match`: true if the predicted function name is the same as ground truth (case-sensitive snake_case).
- `purpose_match`: true if the predicted purpose captures the same intent, even with different wording.
- `inputs_match`: true if the predicted inputs have the same names, types, and descriptions as ground truth. Order doesn't matter.
- `output_match`: true if the predicted output type and description match ground truth.
- `observations_match`: true if all key observations from ground truth are represented in predicted (allow paraphrasing).
- `constraints_match`: true if all constraints from ground truth are present in predicted with equivalent logical meaning.
- `assumptions_match`: true if the predicted assumptions cover the same ground as ground truth.
- `edge_cases_match`: true if the predicted edge cases cover the same boundary conditions as ground truth (exact input values may differ as long as they test the same cases).
- `success_condition_match`: true if the predicted success condition is logically equivalent to ground truth.
- `closed_world_match`: true if the predicted closed_world.confirmed and unresolved_ambiguities match ground truth.

Be strict but fair. Focus on semantic equivalence, not lexical identity.
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end != -1:
        candidate = text[start:end]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse JSON from judge output: {exc}\nRaw: {text}"
            ) from exc

    raise ValueError(f"No JSON object found in judge output:\n{text}")


def judge_schema(
    nl_requirement: str,
    ground_truth_schema: dict,
    predicted_schema: dict,
    model: str = "llama3",
    host: Optional[str] = None,
) -> dict:
    """
    Use an LLM to compare a predicted schema against a ground-truth schema
    given the original natural-language requirement.

    Returns a dict with score, per-field match bools, differences, and reasoning.
    """
    client_kwargs: dict = {}
    if host:
        client_kwargs["host"] = host

    user_prompt = (
        "Evaluate how well the predicted schema matches the ground-truth schema.\n\n"
        f"## Natural Language Requirement\n{nl_requirement}\n\n"
        f"## Ground-Truth Schema\n```json\n{json.dumps(ground_truth_schema, indent=2)}\n```\n\n"
        f"## Predicted Schema\n```json\n{json.dumps(predicted_schema, indent=2)}\n```\n\n"
        "Output ONLY the JSON evaluation object. No markdown, no extra text."
    )

    logger.debug("Sending schema to judge model=%s", model)

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SCHEMA_JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        **client_kwargs,
    )

    content = response["message"]["content"].strip()
    logger.debug("Raw judge response:\n%s", content)

    return _extract_json(content)
