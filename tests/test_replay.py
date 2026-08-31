"""Temporal Jenkins history and replay tests."""

from collections import Counter

from app.data import load_tickets, migration_events
from app.models import IncidentAnalysis, SkillStep, TemporalSkill
from app.replay import evaluate_current_skill


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
            "SSH and systemctl restart on retired Compute Engine VM",
            "Edit local Jenkins controller configuration",
            "Direct Helm upgrade",
            "Persistent direct kubectl mutation",
        ],
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
        stale_reason="The Compute Engine fleet was retired and the advice is obsolete.",
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
    assert len(tickets) == 200
    assert counts == {"vm": 80, "helm": 55, "gitops": 40, "ephemeral": 25}
    assert len(migration_events()) == 3


def test_current_skill_rejects_stale_actions_and_passes_temporal_replay() -> None:
    report = evaluate_current_skill(current_skill(), incident())
    assert report.score == 100
    assert report.verdict == "PASS"
    assert all(report.checks.values())
