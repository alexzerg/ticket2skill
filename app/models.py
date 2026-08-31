"""Typed tickets, generated skills, replay evidence, and registry records."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["RESOLVE", "ESCALATE", "DENY"]
AttributeValue = str | int | bool


class CategorySummary(BaseModel):
    id: str
    name: str
    description: str
    evidence_count: int
    held_out_count: int
    new_count: int


class WorkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = "external-request"
    category: str
    issue: str
    attributes: dict[str, AttributeValue]


class Ticket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: str
    split: Literal["training", "held_out", "new"]
    issue: str
    resolution_notes: str = ""
    attributes: dict[str, AttributeValue]
    required_policy_terms: list[str] = []
    expected_outcome: Decision


class ToolStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tool: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    instruction: str


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    condition: str
    outcome: Decision
    rationale: str


class SkillSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    category: str
    version: str = Field(pattern=r"^v[0-9]+$")
    purpose: str
    inputs: list[str] = Field(min_length=2)
    allowed_tools: list[str] = Field(min_length=3)
    workflow: list[ToolStep] = Field(min_length=3)
    policy_rules: list[PolicyRule]
    success_criteria: list[str] = Field(min_length=2)


class ReplayCase(BaseModel):
    ticket_id: str
    expected: Decision
    actual: Decision
    passed: bool
    tool_trace: list[str]
    finding: str


class ReplayReport(BaseModel):
    skill_name: str
    skill_version: str
    passed: int
    total: int
    score: int
    cases: list[ReplayCase]
    failures: list[str]
    verdict: Literal["PASS", "FAIL"]


class PublishedSkill(BaseModel):
    registry_id: str
    name: str
    category: str
    version: str
    replay_score: int
    firestore_path: str
    artifact_url: str
    execute_url: str
