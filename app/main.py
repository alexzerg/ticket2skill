"""Temporal Jenkins skill compiler API."""

from collections import Counter
from pathlib import Path
from threading import Lock
from typing import Any

import google.cloud.pubsub_v1 as pubsub_v1  # type: ignore[import-untyped]
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents import LOCATION, MODEL, PROJECT, TemporalAgents
from app.data import (
    CURRENT_INCIDENT,
    NEXT_DRIFT_EVENT,
    legacy_exceptions,
    load_tickets,
    migration_events,
)
from app.lifecycle import apply_drift_update
from app.models import (
    ControllerRouteDecision,
    ControllerRouteRequest,
    IncidentAnalysis,
    PublishedTemporalSkill,
    TemporalSkill,
    TimelineAnalysis,
)
from app.registry import artifact_path, publish_drift_update, publish_temporal_skill, skill_path
from app.replay import evaluate_current_skill, evaluate_drift_update
from app.routing import route_controller

app = FastAPI(title="Runbook Drift", version="0.11.1")
state_lock = Lock()
state: dict[str, Any] = {
    "jira_connected": False,
    "tickets_imported": False,
    "timeline": None,
    "result": None,
}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ready",
        "project": PROJECT,
        "location": LOCATION,
        "model": MODEL,
        "framework": "Google GenAI SDK",
    }


@app.post("/api/jira/check")
def check_jira() -> dict[str, Any]:
    """Connect the synthetic Jira source and import the selected resolved issues."""

    tickets = load_tickets()
    with state_lock:
        state["jira_connected"] = True
        state["tickets_imported"] = True
        state["timeline"] = None
        state["result"] = None
    return {
        "connected": True,
        "mode": "synthetic-enterprise-demo",
        "tenant": "Acme Engineering",
        "endpoint": "https://acme-ops.atlassian.net/rest/api/3/search",
        "auth": "OAuth 2.0",
        "project": "OPS",
        "selected_label": "jenkins",
        "jql": ('project = OPS AND labels = "jenkins" AND status = Done ORDER BY resolved ASC'),
        "tickets_loaded": len(tickets),
        "first_issue": tickets[0].id,
        "last_issue": tickets[-1].id,
    }


@app.get("/api/history")
def history() -> dict[str, Any]:
    tickets = load_tickets()
    counts = Counter(ticket.era for ticket in tickets)
    return {
        "system": "Jenkins",
        "ticket_count": len(tickets),
        "era_counts": dict(counts),
        "migrations": [event.model_dump() for event in migration_events()],
        "legacy_exceptions": [exception.model_dump() for exception in legacy_exceptions()],
        "sample_tickets": [
            ticket.model_dump()
            for ticket in [
                tickets[0],
                tickets[79],
                tickets[80],
                tickets[134],
                tickets[135],
                tickets[174],
                tickets[175],
                tickets[-1],
            ]
        ],
        "current_incident": CURRENT_INCIDENT,
        "historical_majority": {
            "era": "vm",
            "tickets": counts["vm"],
            "recommendation": (
                "SSH to the affected Compute Engine VM and restart Jenkins with systemctl."
            ),
        },
    }


@app.post("/api/analyze-timeline")
def analyze_timeline() -> dict[str, Any]:
    if not state.get("tickets_imported"):
        raise HTTPException(status_code=409, detail="check Jira and load tickets first")
    try:
        timeline = TemporalAgents().analyze_timeline(load_tickets(), migration_events())
        with state_lock:
            state["timeline"] = timeline.model_dump()
            state["result"] = None
        return {
            "timeline": timeline.model_dump(),
            "history": history(),
        }
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/build-current-skill")
def build_current_skill() -> dict[str, Any]:
    stored_timeline = state.get("timeline")
    if not isinstance(stored_timeline, dict):
        raise HTTPException(status_code=409, detail="analyze the ticket timeline first")
    try:
        timeline = TimelineAnalysis.model_validate(stored_timeline)
        migrations = migration_events()
        agents = TemporalAgents()
        skill = agents.compile_skill(timeline, migrations)
        incident = agents.resolve_incident(skill, CURRENT_INCIDENT)
        replay = evaluate_current_skill(skill, incident)
        if replay.verdict != "PASS":
            raise RuntimeError(f"temporal replay scored {replay.score}%")
        published = publish_temporal_skill(timeline, skill, incident, replay)
        result = {
            "timeline": timeline.model_dump(),
            "skill": skill.model_dump(),
            "incident": incident.model_dump(),
            "replay": replay.model_dump(),
            "published": published.model_dump(),
        }
        with state_lock:
            state["result"] = result
        return result
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/route-incident")
def route_incident(request: ControllerRouteRequest) -> ControllerRouteDecision:
    current = state.get("result")
    if not isinstance(current, dict):
        raise HTTPException(status_code=409, detail="build the current skill first")
    skill = TemporalSkill.model_validate(current["skill"])
    return route_controller(request.controller, skill)


@app.post("/api/simulate-drift")
def simulate_drift() -> dict[str, Any]:
    current = state.get("result")
    if not isinstance(current, dict):
        raise HTTPException(status_code=409, detail="build the current skill first")
    try:
        previous_skill = TemporalSkill.model_validate(current["skill"])
        if previous_skill.version != "v4":
            raise HTTPException(status_code=409, detail="the drift event is already applied")
        timeline = TimelineAnalysis.model_validate(current["timeline"])
        previous_incident = IncidentAnalysis.model_validate(current["incident"])
        previous_published = PublishedTemporalSkill.model_validate(current["published"])
        publisher = pubsub_v1.PublisherClient()
        topic = publisher.topic_path(PROJECT, "runbook-drift-events")
        message_id = publisher.publish(
            topic,
            NEXT_DRIFT_EVENT.model_dump_json().encode("utf-8"),
            event_type="architecture.drift",
        ).result(timeout=20)
        update = TemporalAgents().update_for_drift(previous_skill, NEXT_DRIFT_EVENT)
        drift_replay = evaluate_drift_update(update)
        if drift_replay.verdict != "PASS":
            raise RuntimeError(f"drift replay scored {drift_replay.score}%")
        current_skill, current_incident = apply_drift_update(
            previous_skill, previous_incident, update
        )
        skill_replay = evaluate_current_skill(current_skill, current_incident)
        if skill_replay.verdict != "PASS":
            raise RuntimeError(f"v5 skill replay scored {skill_replay.score}%")
        current_published = publish_temporal_skill(
            timeline, current_skill, current_incident, skill_replay
        )
        firestore_path = publish_drift_update(
            NEXT_DRIFT_EVENT,
            update,
            drift_replay,
            message_id,
            previous_published.registry_id,
            current_published,
        )
        result = {
            "timeline": timeline.model_dump(),
            "skill": current_skill.model_dump(),
            "incident": current_incident.model_dump(),
            "replay": skill_replay.model_dump(),
            "published": current_published.model_dump(),
        }
        with state_lock:
            state["result"] = result
        return {
            "pubsub_message_id": message_id,
            "event": NEXT_DRIFT_EVENT.model_dump(),
            "previous": {
                "version": previous_skill.version,
                "registry_id": previous_published.registry_id,
                "status": "STALE",
                "reason": update.stale_reason,
            },
            "current": {
                "version": current_skill.version,
                "registry_id": current_published.registry_id,
                "status": "CURRENT",
                "architecture": current_skill.current_architecture,
                "legacy_exceptions": [
                    exception.model_dump() for exception in current_skill.legacy_exceptions
                ],
                "workflow": [step.model_dump() for step in current_skill.workflow],
                "deprecated_actions": current_skill.deprecated_actions,
                "jcasc_patch": current_incident.jcasc_patch,
                "artifact_url": current_published.artifact_url,
                "evidence_bundle_url": current_published.evidence_bundle_url,
                "firestore_path": current_published.firestore_path,
            },
            "replay": drift_replay.model_dump(),
            "skill_replay": skill_replay.model_dump(),
            "firestore_path": firestore_path,
            "summary": {
                "events_processed": 1,
                "skills_invalidated": 1,
                "skills_updated": 1,
                "remaining_temporal_regressions": 0,
            },
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/reset")
def reset() -> dict[str, str]:
    with state_lock:
        state.update(
            jira_connected=False,
            tickets_imported=False,
            timeline=None,
            result=None,
        )
    return {"status": "RESET"}


@app.get("/api/skills/{registry_id}")
def download_skill(registry_id: str) -> FileResponse:
    try:
        path = skill_path(registry_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="skill not found") from error
    version = "v5" if "-v5-" in registry_id else "v4"
    return FileResponse(
        path,
        filename=f"jenkins-current-recovery-{version}.md",
        media_type="text/markdown",
    )


@app.get("/api/artifacts/{registry_id}")
def download_artifact(registry_id: str) -> FileResponse:
    try:
        path = artifact_path(registry_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="artifact not found") from error
    return FileResponse(path, filename=path.name, media_type="application/zip")


STATIC_ROOT = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_ROOT, html=True), name="static")
