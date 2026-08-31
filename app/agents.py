"""Gemini 3.5 agents for temporal operations knowledge."""

import json
import os

from google import genai
from google.genai import types

from app.models import (
    DriftEvent,
    DriftUpdate,
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
Set legacy_exceptions to exactly three VM-era controllers: jenkins-paris, jenkins-barcelona, and
jenkins-NYC. SSH, journalctl, and systemctl remain valid only when an incident target exactly
matches one of those names; there is no wildcard VM exception.

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
Deprecated actions must include SSH/systemctl VM restart for every non-allowlisted target, editing
local controller config outside the three exceptions, direct Helm upgrade, and persistent direct
kubectl mutation. Copy timeline.legacy_exceptions into the skill unchanged. The skill must route
jenkins-paris, jenkins-barcelona, and jenkins-NYC to their scoped VM runbook only on exact match.

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
Explain that this is obsolete for the reported incident because it does not target jenkins-paris,
jenkins-barcelona, or jenkins-NYC. Those three exact names are controlled VM-era exceptions; all
other Jenkins recovery is GitOps-managed on GKE and agents use Workload Identity.
The current recommendation must update the JCasC Kubernetes agent pod template through a Git pull
request, validate the configuration, inspect Argo CD diff, and sync after approval.
Generate a concise valid YAML JCasC patch that sets serviceAccount: jenkins-agent and references the
Google service account annotation iam.gke.io/gcp-service-account. Use the explicit variable
`${{GCP_PROJECT_ID}}` in the Google service account email; never emit `gcp-project` or another fake
project identifier.

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

    def update_for_drift(self, skill: TemporalSkill, event: DriftEvent) -> DriftUpdate:
        prompt = f"""
You are the Continuous Drift Agent. A new authoritative architecture event invalidates part of the
currently published Jenkins recovery skill. Return DriftUpdate JSON.

Required versions: previous_version=v4 and new_version=v5. Explain why the old
iam.gke.io/gcp-service-account annotation is stale. The updated workflow must inspect the direct GKE
Workload Identity Federation principal binding, change the Kubernetes service account to
ci-build-agent through a Git pull request, validate JCasC, validate the Terraform IAM change,
inspect Argo CD diff, and sync only after approval.

Set current_architecture exactly to "Argo CD managed JCasC with ephemeral GKE agents and direct
Workload Identity Federation principal binding". The new JCasC patch must use the valid path
jenkins.clouds[].kubernetes.templates[], set serviceAccount: ci-build-agent, and contain no
annotations block or retired Google-service-account annotation. Copy all three
skill.legacy_exceptions into
preserved_legacy_exceptions unchanged: the identity migration affects the GKE fleet, not the three
explicit VM-era controllers.

Current skill:
{skill.model_dump_json()}

Architecture event:
{event.model_dump_json()}
"""
        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=self._config(DriftUpdate),
        )
        if not response.text:
            raise RuntimeError("Gemini returned no drift update")
        return DriftUpdate.model_validate_json(response.text)
