"""Ticket2Skill API and demo orchestration."""

from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents import LOCATION, MODEL, PROJECT, SkillAgents
from app.data import tickets_for
from app.models import PublishedSkill, ReplayReport, SkillSpec
from app.registry import artifact_path, publish_skill
from app.replay import execute_skill, replay_skill

app = FastAPI(title="Ticket2Skill", version="0.3.3")
state_lock = Lock()
state: dict[str, Any] = {
    "skill_v1": None,
    "report_v1": None,
    "skill_v2": None,
    "report_v2": None,
    "published": None,
}


def _require(name: str, expected_type: type[Any]) -> Any:
    value = state.get(name)
    if not isinstance(value, expected_type):
        raise HTTPException(status_code=409, detail=f"pipeline step missing: {name}")
    return value


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ready",
        "project": PROJECT,
        "location": LOCATION,
        "model": MODEL,
        "framework": "Google GenAI SDK",
        "cloud_service": "Cloud Run + Firestore",
    }


@app.get("/api/tickets")
def tickets() -> dict[str, Any]:
    training = tickets_for("training")
    held_out = tickets_for("held_out")
    new = tickets_for("new")
    return {
        "training": [ticket.model_dump() for ticket in training],
        "held_out": [ticket.model_dump() for ticket in held_out],
        "new": [ticket.model_dump() for ticket in new],
        "counts": {"training": len(training), "held_out": len(held_out), "new": len(new)},
    }


@app.post("/api/reset")
def reset() -> dict[str, str]:
    with state_lock:
        for key in state:
            state[key] = None
    return {"status": "RESET"}


@app.post("/api/discover")
def discover() -> dict[str, Any]:
    try:
        skill = SkillAgents().discover_skill(tickets_for("training"))
        with state_lock:
            state.update(
                skill_v1=skill,
                report_v1=None,
                skill_v2=None,
                report_v2=None,
                published=None,
            )
        return {
            "agent": "Pattern Miner + Skill Builder",
            "model": MODEL,
            "evidence_tickets": len(tickets_for("training")),
            "skill": skill.model_dump(),
        }
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/replay/v1")
def replay_v1() -> dict[str, Any]:
    skill = _require("skill_v1", SkillSpec)
    report = replay_skill(skill, tickets_for("held_out"))
    with state_lock:
        state["report_v1"] = report
    return {
        "agent": "Held-Out Replay",
        "dataset": "unseen enterprise cases",
        "report": report.model_dump(),
    }


@app.post("/api/improve")
def improve() -> dict[str, Any]:
    skill = _require("skill_v1", SkillSpec)
    report = _require("report_v1", ReplayReport)
    if report.verdict == "PASS":
        raise HTTPException(status_code=409, detail="skill v1 has no failures to repair")
    try:
        improved = SkillAgents().repair_skill(skill, report)
        with state_lock:
            state["skill_v2"] = improved
            state["report_v2"] = None
            state["published"] = None
        return {
            "agent": "Replay Critic",
            "failure_count": len(report.failures),
            "skill": improved.model_dump(),
        }
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/replay/v2")
def replay_v2() -> dict[str, Any]:
    skill = _require("skill_v2", SkillSpec)
    report = replay_skill(skill, tickets_for("held_out"))
    with state_lock:
        state["report_v2"] = report
    return {
        "agent": "Regression Gate",
        "dataset": "same held-out cases",
        "report": report.model_dump(),
    }


@app.post("/api/publish")
def publish() -> dict[str, Any]:
    skill = _require("skill_v2", SkillSpec)
    report = _require("report_v2", ReplayReport)
    try:
        published = publish_skill(skill, report)
        with state_lock:
            state["published"] = published
        return {
            "agent": "Registry Publisher",
            "published": published.model_dump(),
        }
    except Exception as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/run-new")
def run_new() -> dict[str, Any]:
    skill = _require("skill_v2", SkillSpec)
    ticket = tickets_for("new")[0]
    result = execute_skill(skill, ticket)
    return {
        "ticket": ticket.model_dump(),
        "execution": result.model_dump(),
        "published": isinstance(state.get("published"), PublishedSkill),
    }


@app.get("/api/artifacts/{registry_id}")
def download_artifact(registry_id: str) -> FileResponse:
    try:
        path = artifact_path(registry_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="artifact not found") from error
    return FileResponse(path, filename=path.name, media_type="application/zip")


STATIC_ROOT = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_ROOT, html=True), name="static")
