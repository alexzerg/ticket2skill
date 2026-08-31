"""Gemini 3.5 agents for temporal operations knowledge."""

import json
import os

from google import genai
from google.genai import types

from app.models import (
    IncidentAnalysis,
    JenkinsTicket,
    MigrationEvent,
    TemporalSkill,
    TimelineAnalysis,
)

MODEL = os.environ.get("TICKET2SKILL_MODEL", "gemini-3.5-flash")
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "ticket2skill-agentic-26")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")


class TemporalAgents:
    """Timeline Miner, Skill Compiler, and Incident Resolver agents."""

    def __init__(self) -> None:
        self.client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)

    def _config(self, schema: type[object], tokens: int = 8192) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=tokens,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

    def analyze_timeline(
        self, tickets: list[JenkinsTicket], migrations: list[MigrationEvent]
    ) -> TimelineAnalysis:
        evidence = [
            {
                "id": ticket.id,
                "resolved_at": ticket.resolved_at,
                "era": ticket.era,
                "architecture": ticket.architecture,
                "issue": ticket.issue,
                "resolution": ticket.resolution,
                "tools": ticket.tools_used,
            }
            for ticket in tickets
        ]
        prompt = f"""
You are the Timeline Miner agent. Analyze all 200 historical Jenkins tickets plus the authoritative
migration change log. Detect exactly four operational eras: vm, helm, gitops, and ephemeral.
Old tickets remain valid historical evidence but their actions may be retired. Return
TimelineAnalysis JSON. Set current_era to ephemeral and source_ticket_count to 200.

Authoritative migration log:
{json.dumps([event.model_dump() for event in migrations], separators=(",", ":"))}

Historical tickets:
{json.dumps(evidence, separators=(",", ":"))}
"""
        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=self._config(TimelineAnalysis),
        )
        if not response.text:
            raise RuntimeError("Gemini returned no timeline")
        return TimelineAnalysis.model_validate_json(response.text)

    def compile_skill(
        self, timeline: TimelineAnalysis, migrations: list[MigrationEvent]
    ) -> TemporalSkill:
        prompt = f"""
You are the Temporal Skill Compiler. Build the current Jenkins recovery skill from the timeline and
migration log. Return TemporalSkill JSON.

Required identity: name=jenkins-current-recovery, version=v4, current_era=ephemeral.
The current architecture is Argo CD managed JCasC with ephemeral GKE agents and Workload Identity.
The workflow must diagnose GKE agent pods and Workload Identity, update the JCasC agent pod template
through a Git pull request, validate JCasC, inspect Argo CD diff, and sync only after approval.
Deprecated actions must include SSH/systemctl VM restart, editing local controller config, direct
Helm upgrade, and persistent direct kubectl mutation.

Timeline:
{timeline.model_dump_json()}

Migration log:
{json.dumps([event.model_dump() for event in migrations], separators=(",", ":"))}
"""
        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=self._config(TemporalSkill),
        )
        if not response.text:
            raise RuntimeError("Gemini returned no temporal skill")
        return TemporalSkill.model_validate_json(response.text)

    def resolve_incident(self, skill: TemporalSkill, incident: str) -> IncidentAnalysis:
        prompt = f"""
You are the Current-Era Incident Resolver. Resolve the new Jenkins incident using only the temporal
skill. Contrast the historical majority answer with the current safe answer.

The stale majority answer must describe SSH to a Compute Engine VM and systemctl restart Jenkins.
Explain that this is obsolete because the VM fleet was retired, Jenkins is GitOps-managed on GKE,
and agents now use Workload Identity.
The current recommendation must update the JCasC Kubernetes agent pod template through a Git pull
request, validate the configuration, inspect Argo CD diff, and sync after approval.
Generate a concise valid YAML JCasC patch that sets serviceAccount: jenkins-agent and references the
Google service account annotation iam.gke.io/gcp-service-account.

Current temporal skill:
{skill.model_dump_json()}

Incident:
{incident}
"""
        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=self._config(IncidentAnalysis),
        )
        if not response.text:
            raise RuntimeError("Gemini returned no incident resolution")
        return IncidentAnalysis.model_validate_json(response.text)
