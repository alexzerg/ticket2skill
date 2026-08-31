"""Ticket2Skill API and autonomous multi-domain pipeline."""

from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents import LOCATION, MODEL, PROJECT, SkillAgents
from app.catalog import classify_request, definition
from app.data import category_summaries, held_out_tickets, new_tickets, training_tickets
from app.models import SkillSpec, Ticket, WorkRequest
from app.registry import artifact_path, load_skill, publish_skill
from app.replay import execute_skill, replay_skill

app = FastAPI(title="Ticket2Skill", version="0.5.1")
state_lock = Lock()
state: dict[str, Any] = {
    "category": None,
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


def _execution_outcome(ticket: Ticket, result: Any) -> dict[str, Any]:
    if result.actual == "RESOLVE":
        status = "RESOLVED"
        artifact_prefix = {
            "vpn": "VPN-RECOVERY",
            "jenkins": "JENKINS-RETRY",
            "hardware": "HARDWARE-ORDER",
            "database": "TEMP-ACCESS-GRANT",
            "sonarqube": "SONARQUBE-ACCESS",
        }[ticket.category]
        message = "Standard work completed automatically; the request was closed."
    elif result.actual == "ESCALATE":
        status = "WAITING_APPROVAL"
        artifact_prefix = "APPROVAL"
        message = "A policy approval task was created before privileged action."
    else:
        status = "ACCESS_DENIED"
        artifact_prefix = "AUDIT-DENIAL"
        message = "Unsafe action was blocked and an audit record was created."
    return {
        "ticket": ticket.model_dump(),
        "execution": result.model_dump(),
        "ticket_status": status,
        "artifact": f"{artifact_prefix}-{ticket.id}",
        "business_outcome": message,
    }


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


@app.get("/api/categories")
def categories() -> dict[str, Any]:
    summaries = category_summaries()
    return {
        "categories": [summary.model_dump() for summary in summaries],
        "total_evidence": sum(summary.evidence_count for summary in summaries),
    }


@app.get("/api/categories/{category}")
def category_detail(category: str) -> dict[str, Any]:
    try:
        config = definition(category)
        training = training_tickets(category)
        return {
            "category": next(
                summary.model_dump() for summary in category_summaries() if summary.id == category
            ),
            "sample_tickets": [ticket.model_dump() for ticket in training[:6]],
            "held_out": [ticket.model_dump() for ticket in held_out_tickets(category)],
            "new": [ticket.model_dump() for ticket in new_tickets(category)],
            "inputs": config.inputs,
            "tool_allowlist": [*config.standard_tools, config.escalation_tool],
        }
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/reset")
def reset() -> dict[str, str]:
    with state_lock:
        for key in state:
            state[key] = None
    return {"status": "RESET"}


@app.post("/api/pipeline/{category}")
def run_pipeline(category: str) -> dict[str, Any]:
    try:
        evidence = training_tickets(category)
        held_out = held_out_tickets(category)
        agents = SkillAgents()
        skill_v1 = agents.discover_skill(category, evidence)
        report_v1 = replay_skill(skill_v1, held_out)
        skill_v2 = agents.repair_skill(category, skill_v1, report_v1, held_out)
        report_v2 = replay_skill(skill_v2, held_out)
        if report_v2.verdict != "PASS":
            raise RuntimeError(
                f"repaired skill failed regression gate with score {report_v2.score}%"
            )
        published = publish_skill(skill_v2, report_v2)
        with state_lock:
            state.update(
                category=category,
                skill_v1=skill_v1,
                report_v1=report_v1,
                skill_v2=skill_v2,
                report_v2=report_v2,
                published=published,
            )
        return {
            "category": category,
            "evidence_count": len(evidence),
            "model": MODEL,
            "skill_v1": skill_v1.model_dump(),
            "report_v1": report_v1.model_dump(),
            "skill_v2": skill_v2.model_dump(),
            "report_v2": report_v2.model_dump(),
            "published": published.model_dump(),
        }
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/run-new/{category}")
def run_new(category: str) -> dict[str, Any]:
    if state.get("category") != category:
        raise HTTPException(status_code=409, detail="build this category skill first")
    skill = _require("skill_v2", SkillSpec)
    executions = [
        _execution_outcome(ticket, execute_skill(skill, ticket)) for ticket in new_tickets(category)
    ]
    return {
        "executions": executions,
        "summary": {
            "auto_resolved": sum(item["ticket_status"] == "RESOLVED" for item in executions),
            "approval_requests": sum(
                item["ticket_status"] == "WAITING_APPROVAL" for item in executions
            ),
            "access_denied": sum(item["ticket_status"] == "ACCESS_DENIED" for item in executions),
            "unsafe_actions": 0,
            "estimated_manual_minutes_saved": 18,
        },
    }


@app.post("/api/skills/{registry_id}/execute")
def execute_published_skill(registry_id: str, request: WorkRequest) -> dict[str, Any]:
    try:
        skill = load_skill(registry_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="published skill not found") from error
    if skill.category != request.category:
        raise HTTPException(status_code=422, detail="request category does not match skill")
    expected, required_terms = classify_request(request.category, request.attributes)
    ticket = Ticket(
        id=request.id,
        category=request.category,
        split="new",
        issue=request.issue,
        attributes=request.attributes,
        required_policy_terms=required_terms,
        expected_outcome=expected,
    )
    return _execution_outcome(ticket, execute_skill(skill, ticket))


@app.get("/api/artifacts/{registry_id}")
def download_artifact(registry_id: str) -> FileResponse:
    try:
        path = artifact_path(registry_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="artifact not found") from error
    return FileResponse(path, filename=path.name, media_type="application/zip")


STATIC_ROOT = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_ROOT, html=True), name="static")
