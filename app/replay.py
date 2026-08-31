"""Deterministic temporal replay and stale-action checks."""

import re

from app.data import LEGACY_JENKINS_INSTANCES
from app.models import (
    DriftUpdate,
    IncidentAnalysis,
    LegacyException,
    TemporalReplayReport,
    TemporalSkill,
)


def legacy_exception_scope_is_bounded(exceptions: list[LegacyException]) -> bool:
    return all(
        exception.era == "vm"
        and exception.controller.lower() in exception.routing_condition.lower()
        and "match" in exception.routing_condition.lower()
        and "exact" in exception.routing_condition.lower()
        and "compute engine" in exception.architecture.lower()
        and "vm" in exception.architecture.lower()
        and "ssh" in " ".join(exception.allowed_actions).lower()
        and "journalctl" in " ".join(exception.allowed_actions).lower()
        and "systemctl" in " ".join(exception.allowed_actions).lower()
        for exception in exceptions
    )


def evaluate_current_skill(
    skill: TemporalSkill, incident: IncidentAnalysis
) -> TemporalReplayReport:
    workflow = " ".join(f"{step.tool} {step.instruction}" for step in skill.workflow).lower()
    deprecated = " ".join(skill.deprecated_actions).lower()
    recommendation = (
        f"{incident.current_recommendation} {' '.join(incident.planned_tool_trace)}"
    ).lower()
    patch = incident.jcasc_patch.lower()
    legacy_names = {exception.controller for exception in skill.legacy_exceptions}
    checks = {
        "current_ephemeral_era": skill.current_era == "ephemeral",
        "legacy_exception_allowlist_exact": legacy_names == set(LEGACY_JENKINS_INSTANCES),
        "legacy_exception_scope_bounded": legacy_exception_scope_is_bounded(
            skill.legacy_exceptions
        ),
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


def evaluate_drift_update(update: DriftUpdate) -> TemporalReplayReport:
    workflow = " ".join(f"{step.tool} {step.instruction}" for step in update.workflow).lower()
    patch = update.jcasc_patch.lower()
    legacy_names = {exception.controller for exception in update.preserved_legacy_exceptions}
    checks = {
        "version_advanced": update.previous_version == "v4" and update.new_version == "v5",
        "legacy_exceptions_preserved": legacy_names == set(LEGACY_JENKINS_INSTANCES),
        "legacy_exception_scope_preserved": legacy_exception_scope_is_bounded(
            update.preserved_legacy_exceptions
        ),
        "retired_annotation_detected": "annotation" in update.stale_reason.lower(),
        "direct_principal_binding": "principal" in workflow
        or "principal" in update.current_architecture.lower(),
        "terraform_change_validated": "terraform" in workflow,
        "git_pull_request_required": "git" in workflow and "pull" in workflow,
        "jcasc_validated": "jcasc" in workflow,
        "argocd_diff_before_sync": "argocd" in workflow and "diff" in workflow,
        "new_service_account": bool(re.search(r"serviceaccount:\s*['\"]?ci-build-agent", patch)),
        "old_annotation_removed": "iam.gke.io/gcp-service-account" not in patch,
    }
    score = round(sum(checks.values()) / len(checks) * 100)
    return TemporalReplayReport(
        score=score,
        checks=checks,
        verdict="PASS" if score == 100 else "FAIL",
    )
