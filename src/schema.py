from typing import List, Optional

from pydantic import BaseModel


class InputField(BaseModel):
    name: str
    type: str
    description: str


class OutputField(BaseModel):
    type: str
    description: str


class Constraint(BaseModel):
    condition: str
    consequence: str


class EdgeCase(BaseModel):
    input: str
    expected_output: str
    reason: str


class ClosedWorld(BaseModel):
    confirmed: bool
    unresolved_ambiguities: List[str]


class RequirementSchema(BaseModel):
    function_name: str
    purpose: str
    inputs: List[InputField]
    output: OutputField
    observations: List[str]
    constraints: List[Constraint]
    assumptions: List[str]
    edge_cases: List[EdgeCase]
    success_condition: str
    closed_world: ClosedWorld
    backdoor_note: Optional[str] = None
