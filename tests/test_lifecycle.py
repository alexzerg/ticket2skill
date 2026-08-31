"""Complete v4 to v5 lifecycle tests."""

from app.data import legacy_exceptions
from app.lifecycle import apply_drift_update
from app.models import DriftUpdate, IncidentAnalysis, SkillStep, TemporalSkill
from app.replay import evaluate_current_skill, evaluate_drift_update


def previous_skill() -> TemporalSkill:
    return TemporalSkill(
        name="jenkins-current-recovery",
        version="v4",
        current_era="ephemeral",
        current_architecture="GKE agents using Google service account impersonation",
        source_ticket_count=200,
        workflow=[
            SkillStep(id="inspect", tool="gke.inspect", instruction="Inspect Workload Identity."),
            SkillStep(id="edit", tool="git.pull-request", instruction="Update JCasC."),
            SkillStep(id="validate", tool="jcasc.validate", instruction="Validate JCasC."),
            SkillStep(id="diff", tool="argocd.diff", instruction="Inspect Argo CD diff."),
        ],
        deprecated_actions=["SSH systemctl restart", "direct Helm", "direct kubectl"],
        legacy_exceptions=legacy_exceptions(),
        temporal_rules=["Use the current architecture", "Respect migrations", "Exact exceptions"],
        success_criteria=["Agents ready", "Diff approved", "No stale action"],
    )


def incident() -> IncidentAnalysis:
    return IncidentAnalysis(
        incident="Queued builds",
        stale_majority_answer="Restart VM",
        stale_reason="The default VM route is retired.",
        current_recommendation="Use the current workflow.",
        planned_tool_trace=["gke", "git", "argocd"],
        jcasc_patch="iam.gke.io/gcp-service-account: agent@gcp-project.iam.gserviceaccount.com",
    )


def drift_update() -> DriftUpdate:
    return DriftUpdate(
        event_id="ARCH-2026-09-WIF",
        previous_version="v4",
        new_version="v5",
        stale_reason="The Google service account annotation and impersonation are retired.",
        retired_actions=["iam.gke.io/gcp-service-account annotation"],
        current_architecture=(
            "Argo CD managed JCasC with ephemeral GKE agents and direct Workload Identity "
            "Federation principal binding"
        ),
        preserved_legacy_exceptions=legacy_exceptions(),
        workflow=[
            SkillStep(id="inspect", tool="gke.inspect", instruction="Inspect agent pods."),
            SkillStep(
                id="iam",
                tool="workload-identity.principal",
                instruction="Verify direct Workload Identity principal binding for ci-build-agent.",
            ),
            SkillStep(
                id="tf",
                tool="terraform.validate",
                instruction="Validate direct principal IAM changes.",
            ),
            SkillStep(id="git", tool="git.pull-request", instruction="Update JCasC in Git."),
            SkillStep(id="jcasc", tool="jcasc.validate", instruction="Validate JCasC."),
            SkillStep(
                id="argocd", tool="argocd.diff", instruction="Inspect Argo CD diff before sync."
            ),
        ],
        jcasc_patch=(
            "jenkins:\n  clouds:\n    - kubernetes:\n        templates:\n"
            "          - name: jenkins-agent\n            serviceAccount: ci-build-agent\n"
        ),
    )


def test_drift_creates_new_v5_without_mutating_v4() -> None:
    previous = previous_skill()
    update = drift_update()
    drift_report = evaluate_drift_update(update)
    assert drift_report.verdict == "PASS"
    current, current_incident = apply_drift_update(previous, incident(), update)
    assert previous.version == "v4"
    assert current.version == "v5"
    assert current.supersedes == "v4"
    assert current.architecture_event == update.event_id
    assert current.legacy_exceptions == previous.legacy_exceptions
    assert "iam.gke.io/gcp-service-account" not in current_incident.jcasc_patch
    assert "serviceAccount: ci-build-agent" in current_incident.jcasc_patch
    assert evaluate_current_skill(current, current_incident).verdict == "PASS"
