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
from app.data import CURRENT_INCIDENT, NEXT_DRIFT_EVENT, load_tickets, migration_events
from app.models import TemporalSkill, TimelineAnalysis
from app.registry import artifact_path, publish_drift_update, publish_temporal_skill
from app.replay import evaluate_current_skill, evaluate_drift_update

app = FastAPI(title="Runbook Drift", version="0.8.0")
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


@app.post("/api/simulate-drift")
def simulate_drift() -> dict[str, Any]:
    current = state.get("result")
    if not isinstance(current, dict):
        raise HTTPException(status_code=409, detail="build the current skill first")
    try:
        publisher = pubsub_v1.PublisherClient()
        topic = publisher.topic_path(PROJECT, "runbook-drift-events")
        message_id = publisher.publish(
            topic,
            NEXT_DRIFT_EVENT.model_dump_json().encode("utf-8"),
            event_type="architecture.drift",
        ).result(timeout=20)
        skill = TemporalSkill.model_validate(current["skill"])
        update = TemporalAgents().update_for_drift(skill, NEXT_DRIFT_EVENT)
        replay = evaluate_drift_update(update)
        if replay.verdict != "PASS":
            raise RuntimeError(f"drift replay scored {replay.score}%")
        firestore_path = publish_drift_update(NEXT_DRIFT_EVENT, update, replay, message_id)
        return {
            "pubsub_message_id": message_id,
            "event": NEXT_DRIFT_EVENT.model_dump(),
            "previous": {
                "version": "v4",
                "status": "STALE",
                "reason": update.stale_reason,
            },
            "current": {
                "version": update.new_version,
                "status": "CURRENT",
                "architecture": update.current_architecture,
                "workflow": [step.model_dump() for step in update.workflow],
                "jcasc_patch": update.jcasc_patch,
            },
            "replay": replay.model_dump(),
            "firestore_path": firestore_path,
            "summary": {
                "events_processed": 1,
                "skills_invalidated": 1,
                "skills_updated": 1,
                "remaining_temporal_regressions": 0,
            },
        }
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


@app.get("/api/artifacts/{registry_id}")
def download_artifact(registry_id: str) -> FileResponse:
    try:
        path = artifact_path(registry_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="artifact not found") from error
    return FileResponse(path, filename=path.name, media_type="application/zip")


STATIC_ROOT = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_ROOT, html=True), name="static")
