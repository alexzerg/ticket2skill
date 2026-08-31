"""Deterministic temporal replay and stale-action checks."""

import re

from app.models import IncidentAnalysis, TemporalReplayReport, TemporalSkill


def evaluate_current_skill(
    skill: TemporalSkill, incident: IncidentAnalysis
) -> TemporalReplayReport:
    workflow = " ".join(f"{step.tool} {step.instruction}" for step in skill.workflow).lower()
    deprecated = " ".join(skill.deprecated_actions).lower()
    recommendation = (
        f"{incident.current_recommendation} {' '.join(incident.planned_tool_trace)}"
    ).lower()
    patch = incident.jcasc_patch.lower()
    checks = {
        "current_ephemeral_era": skill.current_era == "ephemeral",
        "gke_agent_diagnostics": "gke" in workflow or "kubernetes" in workflow,
        "workload_identity_checked": "workload" in workflow and "identity" in workflow,
        "git_pull_request_required": "git" in workflow and "pull" in workflow,
        "jcasc_validated": "jcasc" in workflow,
        "argocd_diff_before_sync": "argocd" in recommendation and "diff" in recommendation,
        "vm_restart_deprecated": "ssh" in deprecated and "systemctl" in deprecated,
        "direct_helm_deprecated": "helm" in deprecated,
        "jcasc_patch_service_account": bool(
            re.search(r"serviceaccount:\s*['\"]?jenkins-agent", patch)
        ),
        "workload_identity_annotation": "iam.gke.io/gcp-service-account" in patch,
        "stale_majority_rejected": "obsolete" in incident.stale_reason.lower()
        or "retired" in incident.stale_reason.lower(),
    }
    score = round(sum(checks.values()) / len(checks) * 100)
    return TemporalReplayReport(
        score=score,
        checks=checks,
        verdict="PASS" if score == 100 else "FAIL",
    )
