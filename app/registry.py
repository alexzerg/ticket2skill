"""Firestore publication and portable temporal skill packages."""

import json
import os
import zipfile
from pathlib import Path
from uuid import uuid4

import yaml
from google.cloud import firestore

from app.agents import MODEL, PROJECT
from app.models import (
    DriftEvent,
    DriftUpdate,
    IncidentAnalysis,
    PublishedTemporalSkill,
    TemporalReplayReport,
    TemporalSkill,
    TimelineAnalysis,
)

ARTIFACT_ROOT = Path(os.environ.get("TICKET2SKILL_ARTIFACT_ROOT", "artifacts"))


def _render_legacy_action(controller: str, action: str) -> str:
    normalized = action.strip().lower()
    if normalized in {"gcloud.compute.ssh", "ssh"}:
        return (
            f"`gcloud compute ssh {controller} --project ${{GCP_PROJECT_ID}} "
            "--zone ${GCE_ZONE}` — connect only to this allowlisted VM."
        )
    if normalized == "journalctl":
        return "`sudo journalctl -u jenkins --since '-15 min'` — diagnose before restart."
    if normalized == "systemctl":
        return "`sudo systemctl restart jenkins` — run only after diagnosis and approval."
    if normalized == "local-config-edit":
        return (
            "Edit only this controller's approved local configuration; back it up and validate "
            "before restarting Jenkins."
        )
    return action


def _normalize_patch(patch: str) -> str:
    return patch.replace("gcp-project", "${GCP_PROJECT_ID}")


def render_skill_markdown(
    timeline: TimelineAnalysis,
    skill: TemporalSkill,
    incident: IncidentAnalysis,
    report: TemporalReplayReport,
) -> str:
    """Render the complete executable skill as one portable Markdown file."""
    workflow = "\n".join(
        f"{number}. **{step.tool}** — {step.instruction}"
        for number, step in enumerate(skill.workflow, start=1)
    )
    exceptions = "\n\n".join(
        "\n".join(
            [
                f"### {exception.controller}",
                f"- Route condition: {exception.routing_condition}",
                f"- Architecture: {exception.architecture}",
                *[
                    f"- Allowed: {_render_legacy_action(exception.controller, action)}"
                    for action in exception.allowed_actions
                ],
            ]
        )
        for exception in skill.legacy_exceptions
    )
    deprecated = "\n".join(f"- {action}" for action in skill.deprecated_actions)
    criteria = "\n".join(f"- {item}" for item in skill.success_criteria)
    lineage_metadata = ""
    lineage_details = ""
    if skill.supersedes and skill.architecture_event:
        lineage_metadata = (
            f"supersedes: {skill.supersedes}\narchitecture_event: {skill.architecture_event}\n"
        )
        lineage_details = (
            f"- Supersedes: {skill.supersedes}\n- Architecture event: {skill.architecture_event}\n"
        )
    patch = _normalize_patch(incident.jcasc_patch).rstrip()
    return f"""---
name: {skill.name}
version: {skill.version}
{lineage_metadata}description: Temporal Jenkins recovery with exact legacy exceptions
current_era: {skill.current_era}
source_ticket_count: {timeline.source_ticket_count}
replay_score: {report.score}
required_inputs:
  - controller_name
  - gcp_project_id
  - gce_zone
  - approval_reference
---

# Jenkins Current Recovery

## Purpose

Resolve Jenkins incidents using the current architecture. Migration evidence outranks historical
ticket frequency. Never apply an old procedure unless an exact legacy exception below matches.

## Required inputs

- `controller_name`: exact Jenkins controller identifier from the incident.
- `GCP_PROJECT_ID`: Google Cloud project containing the relevant Jenkins resources.
- `GCE_ZONE`: required only for one of the three retained VM controllers.
- `approval_reference`: required before restart or Argo CD sync.

## Routing policy

1. Extract the Jenkins controller identifier from the incident.
2. Compare it case-sensitively with the exact legacy exceptions below.
3. On an exact match, use only that controller's scoped VM actions.
4. Otherwise follow the current GKE/JCasC/GitOps workflow.

## Exact legacy exceptions

{exceptions}

## Current architecture

{skill.current_architecture}

## Current workflow

{workflow}

## Deprecated by default

{deprecated}

## Guardrails

- Never reuse a legacy action for a non-allowlisted controller.
- Never perform a persistent direct Kubernetes or Helm mutation.
- Validate Terraform, JCasC, and Argo CD diff before synchronization.
- Require `approval_reference` before service restart or Argo CD sync.

## Incident example

{incident.incident}

Recommended response: {incident.current_recommendation}

## JCasC patch template

```yaml
{patch}
```

## Success criteria

{criteria}

## Provenance

- Historical tickets analyzed: {timeline.source_ticket_count}
- Architecture eras discovered: {len(timeline.eras)}
- Current era: {timeline.current_era}
{lineage_details}- Deterministic replay: {report.score}% ({report.verdict})
- Generator model: {MODEL}
"""


def publish_temporal_skill(
    timeline: TimelineAnalysis,
    skill: TemporalSkill,
    incident: IncidentAnalysis,
    report: TemporalReplayReport,
) -> PublishedTemporalSkill:
    if report.verdict != "PASS":
        raise ValueError("temporal replay gate must pass before publication")
    registry_id = f"{skill.name}-{skill.version}-{uuid4().hex[:8]}"
    package_dir = ARTIFACT_ROOT / registry_id
    package_dir.mkdir(parents=True, exist_ok=False)
    skill_markdown = render_skill_markdown(timeline, skill, incident, report)
    (package_dir / "SKILL.md").write_text(skill_markdown, encoding="utf-8")
    (package_dir / "skill.yaml").write_text(
        yaml.safe_dump(skill.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
    )
    (package_dir / "timeline.json").write_text(timeline.model_dump_json(indent=2), encoding="utf-8")
    (package_dir / "deprecated-actions.json").write_text(
        json.dumps(skill.deprecated_actions, indent=2), encoding="utf-8"
    )
    (package_dir / "legacy-exceptions.json").write_text(
        json.dumps(
            [exception.model_dump(mode="json") for exception in skill.legacy_exceptions],
            indent=2,
        ),
        encoding="utf-8",
    )
    (package_dir / "jcasc-patch.yaml").write_text(
        _normalize_patch(incident.jcasc_patch), encoding="utf-8"
    )
    (package_dir / "eval-report.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    (package_dir / "README.md").write_text(
        f"# Jenkins Current Recovery {skill.version}\n\n"
        "Use SKILL.md as the executable artifact. Other files are publication evidence.\n",
        encoding="utf-8",
    )
    zip_path = ARTIFACT_ROOT / f"{registry_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(package_dir.iterdir()):
            archive.write(file_path, arcname=f"{skill.name}-{skill.version}/{file_path.name}")
    firestore_path = f"temporal_skills/{registry_id}"
    client = firestore.Client(project=PROJECT)
    client.document(firestore_path).set(
        {
            "timeline": timeline.model_dump(mode="json"),
            "skill": skill.model_dump(mode="json"),
            "incident": incident.model_dump(mode="json"),
            "replay": report.model_dump(mode="json"),
            "model": MODEL,
            "status": "CURRENT",
            "skill_file": f"{registry_id}/SKILL.md",
            "skill_markdown": skill_markdown,
            "evidence_bundle": zip_path.name,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )
    client.document("temporal_skills/jenkins-current-recovery-current").set(
        {
            "registry_id": registry_id,
            "version": skill.version,
            "firestore_path": firestore_path,
            "replay_score": report.score,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
    )
    return PublishedTemporalSkill(
        registry_id=registry_id,
        firestore_path=firestore_path,
        artifact_url=f"/api/skills/{registry_id}",
        evidence_bundle_url=f"/api/artifacts/{registry_id}",
        source_ticket_count=timeline.source_ticket_count,
        current_era=skill.current_era,
        replay_score=report.score,
    )


def publish_drift_update(
    event: DriftEvent,
    update: DriftUpdate,
    report: TemporalReplayReport,
    message_id: str,
    previous_registry_id: str,
    current_published: PublishedTemporalSkill,
) -> str:
    if report.verdict != "PASS":
        raise ValueError("drift replay gate must pass before publication")
    client = firestore.Client(project=PROJECT)
    client.document(f"temporal_skills/{previous_registry_id}").set(
        {
            "status": "STALE",
            "invalidated_by": event.event_id,
            "superseded_by": current_published.registry_id,
            "invalidated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    path = f"drift_events/{event.event_id}-{uuid4().hex[:8]}"
    client.document(path).set(
        {
            "event": event.model_dump(mode="json"),
            "update": update.model_dump(mode="json"),
            "replay": report.model_dump(mode="json"),
            "previous_registry_id": previous_registry_id,
            "current_publication": current_published.model_dump(mode="json"),
            "pubsub_message_id": message_id,
            "model": MODEL,
            "status": "APPLIED",
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )
    return path


def skill_path(registry_id: str) -> Path:
    path = (ARTIFACT_ROOT / registry_id / "SKILL.md").resolve()
    root = ARTIFACT_ROOT.resolve()
    if root not in path.parents or not path.is_file():
        raise FileNotFoundError(registry_id)
    return path


def artifact_path(registry_id: str) -> Path:
    path = (ARTIFACT_ROOT / f"{registry_id}.zip").resolve()
    root = ARTIFACT_ROOT.resolve()
    if root not in path.parents or not path.is_file():
        raise FileNotFoundError(registry_id)
    return path
