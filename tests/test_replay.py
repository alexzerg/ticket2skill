"""Temporal Jenkins history and replay tests."""

from collections import Counter

from app.data import LEGACY_JENKINS_INSTANCES, legacy_exceptions, load_tickets, migration_events
from app.models import DriftUpdate, IncidentAnalysis, SkillStep, TemporalSkill
from app.replay import evaluate_current_skill, evaluate_drift_update


def current_skill() -> TemporalSkill:
    return TemporalSkill(
        name="jenkins-current-recovery",
        version="v4",
        current_era="ephemeral",
        current_architecture=(
            "Argo CD managed JCasC with ephemeral GKE agents and Workload Identity"
        ),
        source_ticket_count=200,
        workflow=[
            SkillStep(
                id="diagnose",
                tool="gke.agent-diagnostics",
                instruction="Inspect Kubernetes agent pods.",
            ),
            SkillStep(
                id="identity",
                tool="workload-identity.inspect",
                instruction="Check Workload Identity binding.",
            ),
            SkillStep(
                id="pr",
                tool="git.pull-request",
                instruction="Open Git pull request with JCasC update.",
            ),
            SkillStep(
                id="validate", tool="jcasc.validate", instruction="Validate JCasC configuration."
            ),
            SkillStep(
                id="diff", tool="argocd.diff", instruction="Inspect Argo CD diff before sync."
            ),
            SkillStep(id="sync", tool="argocd.sync", instruction="Sync after approval."),
        ],
        deprecated_actions=[
            "SSH and systemctl restart on non-allowlisted Compute Engine VM",
            "Edit local Jenkins controller configuration outside the allowlist",
            "Direct Helm upgrade",
            "Persistent direct kubectl mutation",
        ],
        legacy_exceptions=legacy_exceptions(),
        temporal_rules=[
            "Use only the current architecture era.",
            "Migration log overrides older ticket frequency.",
            "Git remains the source of truth.",
        ],
        success_criteria=[
            "Ephemeral agent authenticates",
            "Argo CD is healthy",
            "No direct persistent mutation",
        ],
    )


def incident() -> IncidentAnalysis:
    return IncidentAnalysis(
        incident="Ephemeral Jenkins agents cannot authenticate.",
        stale_majority_answer="SSH to a VM and systemctl restart Jenkins.",
        stale_reason=(
            "The target is not one of the three retained VM exceptions, so the advice is obsolete."
        ),
        current_recommendation=(
            "Update JCasC through Git, validate, inspect Argo CD diff, and sync."
        ),
        planned_tool_trace=[
            "gke.agent-diagnostics",
            "workload-identity.inspect",
            "git.pull-request",
            "jcasc.validate",
            "argocd.diff",
            "argocd.sync",
        ],
        jcasc_patch=(
            "serviceAccount: jenkins-agent\n"
            "annotations:\n"
            "  iam.gke.io/gcp-service-account: jenkins-agent@example.iam.gserviceaccount.com\n"
        ),
    )


def test_history_has_200_tickets_across_four_architecture_eras() -> None:
    tickets = load_tickets()
    counts = Counter(ticket.era for ticket in tickets)
    exceptions = legacy_exceptions()
    assert len(tickets) == 200
    assert counts == {"vm": 80, "helm": 55, "gitops": 40, "ephemeral": 25}
    assert len(migration_events()) == 3
    assert tuple(exception.controller for exception in exceptions) == LEGACY_JENKINS_INSTANCES
    assert all(exception.era == "vm" for exception in exceptions)


def test_current_skill_rejects_stale_actions_and_passes_temporal_replay() -> None:
    report = evaluate_current_skill(current_skill(), incident())
    assert report.score == 100
    assert report.verdict == "PASS"
    assert all(report.checks.values())


def test_replay_rejects_an_incomplete_legacy_allowlist() -> None:
    skill = current_skill()
    skill.legacy_exceptions[2] = skill.legacy_exceptions[0].model_copy()
    report = evaluate_current_skill(skill, incident())
    assert report.verdict == "FAIL"
    assert not report.checks["legacy_exception_allowlist_exact"]


def test_drift_update_retires_old_identity_annotation() -> None:
    update = DriftUpdate(
        event_id="ARCH-2026-09-WIF",
        previous_version="v4",
        new_version="v5",
        stale_reason="The old Google service account annotation is retired.",
        retired_actions=["iam.gke.io annotation"],
        current_architecture="Direct Workload Identity Federation principal binding",
        preserved_legacy_exceptions=legacy_exceptions(),
        workflow=[
            SkillStep(
                id="inspect", tool="gke.principal.inspect", instruction="Inspect principal binding."
            ),
            SkillStep(
                id="terraform", tool="terraform.plan", instruction="Validate Terraform IAM change."
            ),
            SkillStep(id="pr", tool="git.pull-request", instruction="Open Git pull request."),
            SkillStep(id="jcasc", tool="jcasc.validate", instruction="Validate JCasC."),
            SkillStep(id="diff", tool="argocd.diff", instruction="Inspect Argo CD diff."),
        ],
        jcasc_patch=(
            "jenkins:\n  clouds:\n    - kubernetes:\n        templates:\n"
            "          - name: jenkins-agent\n            serviceAccount: ci-build-agent\n"
        ),
    )
    report = evaluate_drift_update(update)
    assert report.score == 100
    assert report.verdict == "PASS"
