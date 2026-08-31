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


def publish_temporal_skill(
    timeline: TimelineAnalysis,
    skill: TemporalSkill,
    incident: IncidentAnalysis,
    report: TemporalReplayReport,
) -> PublishedTemporalSkill:
    if report.verdict != "PASS":
        raise ValueError("temporal replay gate must pass before publication")
    registry_id = f"jenkins-current-recovery-v4-{uuid4().hex[:8]}"
    package_dir = ARTIFACT_ROOT / registry_id
    package_dir.mkdir(parents=True, exist_ok=False)
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
    (package_dir / "jcasc-patch.yaml").write_text(incident.jcasc_patch, encoding="utf-8")
    (package_dir / "eval-report.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    (package_dir / "README.md").write_text(
        "# Jenkins Current Recovery v4\n\n"
        "Generated from 200 historical tickets across four architecture eras.\n\n"
        "This skill rejects VM, systemctl, direct Helm, and persistent kubectl advice by default.\n"
        "The only VM-era exceptions are jenkins-paris, jenkins-barcelona, and jenkins-NYC; "
        "their scoped SSH/systemctl runbook is allowed only on exact target match.\n"
        "The current workflow uses JCasC, Git pull requests, Argo CD, ephemeral GKE agents, "
        "and Workload Identity.\n",
        encoding="utf-8",
    )
    zip_path = ARTIFACT_ROOT / f"{registry_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(package_dir.iterdir()):
            archive.write(file_path, arcname=f"jenkins-current-recovery-v4/{file_path.name}")

    firestore_path = f"temporal_skills/{registry_id}"
    firestore.Client(project=PROJECT).document(firestore_path).set(
        {
            "timeline": timeline.model_dump(mode="json"),
            "skill": skill.model_dump(mode="json"),
            "incident": incident.model_dump(mode="json"),
            "replay": report.model_dump(mode="json"),
            "model": MODEL,
            "status": "PUBLISHED",
            "artifact": zip_path.name,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )
    return PublishedTemporalSkill(
        registry_id=registry_id,
        firestore_path=firestore_path,
        artifact_url=f"/api/artifacts/{registry_id}",
        source_ticket_count=timeline.source_ticket_count,
        current_era=skill.current_era,
        replay_score=report.score,
    )


def publish_drift_update(
    event: DriftEvent,
    update: DriftUpdate,
    report: TemporalReplayReport,
    message_id: str,
) -> str:
    if report.verdict != "PASS":
        raise ValueError("drift replay gate must pass before publication")
    path = f"temporal_skills/jenkins-current-recovery-{update.new_version}"
    firestore.Client(project=PROJECT).document(path).set(
        {
            "event": event.model_dump(mode="json"),
            "update": update.model_dump(mode="json"),
            "replay": report.model_dump(mode="json"),
            "pubsub_message_id": message_id,
            "model": MODEL,
            "status": "CURRENT",
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )
    return path


def artifact_path(registry_id: str) -> Path:
    path = (ARTIFACT_ROOT / f"{registry_id}.zip").resolve()
    root = ARTIFACT_ROOT.resolve()
    if root not in path.parents or not path.is_file():
        raise FileNotFoundError(registry_id)
    return path
