import json
import logging
from typing import Optional

import ollama

from .schema import RequirementSchema

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert software requirements analyst and specification writer.

Given a natural-language description of a software function, you must analyze it thoroughly and produce a structured JSON specification that captures all functional and non-functional requirements, edge cases, and constraints.

You MUST output ONLY a single JSON object. No markdown, no explanations, no extra text before or after the JSON.

The JSON must conform exactly to this schema:

{
  "function_name": "<string>",
  "purpose": "<string>",
  "inputs": [
    {
      "name": "<string>",
      "type": "<string>",
      "description": "<string>"
    }
  ],
  "output": {
    "type": "<string>",
    "description": "<string>"
  },
  "observations": ["<string>"],
  "constraints": [
    {
      "condition": "<string>",
      "consequence": "<string>"
    }
  ],
  "assumptions": ["<string>"],
  "edge_cases": [
    {
      "input": "<string>",
      "expected_output": "<string>",
      "reason": "<string>"
    }
  ],
  "success_condition": "<string>",
  "closed_world": {
    "confirmed": <boolean>,
    "unresolved_ambiguities": ["<string>"]
  },
  "backdoor_note": "<string or null>"
}

Field definitions:
- function_name: A valid snake_case function name derived from the requirement.
- purpose: A concise one-sentence description of what the function does.
- inputs: Array of input parameters. Each must have name, type (e.g., "string", "int", "bool"), and description.
- output: Object describing the return type and meaning.
- observations: Factual statements about the behavior derived from the requirement.
- constraints: Logical rules expressed as condition/consequence pairs. Use clear boolean logic.
- assumptions: Things you assume because the requirement is silent or ambiguous.
- edge_cases: Specific test cases. input is the exact value (as a JSON string). expected_output is the string "true" or "false". reason explains why.
- success_condition: A single string representing the exact logical formula for a true return value.
- closed_world.confirmed: true if the requirement is fully and unambiguously specified; false if there are open ambiguities.
- closed_world.unresolved_ambiguities: Array of strings describing ambiguities. Empty if confirmed is true.
- backdoor_note: Describe any natural backdoor (e.g., off-by-one risk, missing check) or null if none exists.

Rules:
1. Base every field strictly on the provided natural language requirement.
2. Do not invent requirements that are not stated.
3. For constraints, break down the logic into atomic conditions.
4. For edge_cases, include empty inputs, boundary values, and invalid types where relevant.
5. Ensure the JSON is syntactically valid. Escape quotes properly.
6. Do NOT wrap the JSON in markdown code fences.
7. Do NOT include any text before the opening { or after the closing }.
"""


def _extract_json(text: str) -> dict:
    """Extract and parse a JSON object from raw LLM text."""
    text = text.strip()

    # Remove common markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop the first fence line (e.g. ```json or ```)
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # Drop the last fence line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: extract the first {...} block
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end != -1:
        candidate = text[start:end]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse JSON from LLM output: {exc}\nRaw: {text}"
            ) from exc

    raise ValueError(f"No JSON object found in LLM output:\n{text}")


def generate_requirement_schema(
    user_prompt: str,
    model: str = "llama3",
    host: Optional[str] = None,
) -> RequirementSchema:
    """
    Send a natural-language requirement to an Ollama LLM and return a
    structured, validated RequirementSchema.

    Args:
        user_prompt: The natural language requirement to analyse.
        model: Ollama model tag (default: "llama3").
        host: Optional Ollama host URL (defaults to library default).

    Returns:
        RequirementSchema: The parsed and validated specification.

    Raises:
        RuntimeError: If the LLM response cannot be parsed or validated.
    """
    client_kwargs: dict = {}
    if host:
        client_kwargs["host"] = host

    logger.debug("Sending requirement to Ollama model=%s", model)

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        **client_kwargs,
    )

    content = response["message"]["content"]
    logger.debug("Raw LLM response:\n%s", content)

    data = _extract_json(content)

    try:
        schema = RequirementSchema.model_validate(data)
    except Exception as exc:
        raise RuntimeError(
            f"LLM output does not match the required schema: {exc}\nData: {data}"
        ) from exc

    return schema
