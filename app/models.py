"""Typed tickets, generated skills, replay evidence, and registry records."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Ticket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    split: Literal["training", "held_out", "new"]
    requester_type: Literal["employee", "contractor"]
    employment_status: Literal["active", "terminated"]
    manager_approval: bool
    issue: str
    resolution_notes: str = ""
    expected_outcome: Literal["RESOLVE", "ESCALATE", "DENY"]


class ToolStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tool: Literal[
        "identity.lookup",
        "employment.verify",
        "manager.request_approval",
        "vpn.revoke_sessions",
        "vpn.issue_recovery",
        "audit.record",
    ]
    instruction: str


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    condition: str
    outcome: Literal["RESOLVE", "ESCALATE", "DENY"]
    rationale: str


class SkillSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    version: str = Field(pattern=r"^v[0-9]+$")
    purpose: str
    inputs: list[str] = Field(min_length=3)
    allowed_tools: list[str] = Field(min_length=3)
    workflow: list[ToolStep] = Field(min_length=3)
    policy_rules: list[PolicyRule]
    success_criteria: list[str] = Field(min_length=2)


class ReplayCase(BaseModel):
    ticket_id: str
    expected: Literal["RESOLVE", "ESCALATE", "DENY"]
    actual: Literal["RESOLVE", "ESCALATE", "DENY"]
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
    version: str
    replay_score: int
    firestore_path: str
    artifact_url: str
