"""Temporal Jenkins operations models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EraId = Literal["vm", "helm", "gitops", "ephemeral"]


class JenkinsTicket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    resolved_at: str
    era: EraId
    architecture: str
    issue: str
    resolution: str
    tools_used: list[str]


class MigrationEvent(BaseModel):
    effective_date: str
    from_architecture: str
    to_architecture: str
    policy_change: str


class EraSummary(BaseModel):
    id: EraId
    label: str
    period: str
    architecture: str
    ticket_count: int
    dominant_resolution: str
    valid_tools: list[str]
    current: bool


class TimelineAnalysis(BaseModel):
    system: Literal["Jenkins"]
    source_ticket_count: int
    eras: list[EraSummary] = Field(min_length=4, max_length=4)
    current_era: Literal["ephemeral"]
    key_finding: str


class SkillStep(BaseModel):
    id: str
    instruction: str
    tool: str


class TemporalSkill(BaseModel):
    name: Literal["jenkins-current-recovery"]
    version: Literal["v4", "v5"]
    current_era: Literal["ephemeral"]
    current_architecture: str
    source_ticket_count: int
    workflow: list[SkillStep] = Field(min_length=4)
    deprecated_actions: list[str] = Field(min_length=3)
    temporal_rules: list[str] = Field(min_length=3)
    success_criteria: list[str] = Field(min_length=3)


class IncidentAnalysis(BaseModel):
    incident: str
    stale_majority_answer: str
    stale_reason: str
    current_recommendation: str
    planned_tool_trace: list[str] = Field(min_length=3)
    jcasc_patch: str


class TemporalReplayReport(BaseModel):
    score: int
    checks: dict[str, bool]
    verdict: Literal["PASS", "FAIL"]


class PublishedTemporalSkill(BaseModel):
    registry_id: str
    firestore_path: str
    artifact_url: str
    source_ticket_count: int
    current_era: str
    replay_score: int


class DriftEvent(BaseModel):
    event_id: str
    effective_date: str
    source: Literal["git", "argocd", "gcp"]
    title: str
    change: str
    retired_configuration: str
    new_configuration: str


class DriftUpdate(BaseModel):
    event_id: str
    previous_version: Literal["v4"]
    new_version: Literal["v5"]
    stale_reason: str
    retired_actions: list[str] = Field(min_length=1)
    current_architecture: str
    workflow: list[SkillStep] = Field(min_length=4)
    jcasc_patch: str
