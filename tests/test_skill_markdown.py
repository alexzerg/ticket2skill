"""Self-contained skill artifact tests."""

from app.data import legacy_exceptions
from app.models import (
    EraSummary,
    IncidentAnalysis,
    SkillStep,
    TemporalReplayReport,
    TemporalSkill,
    TimelineAnalysis,
)
from app.registry import render_skill_markdown


def test_skill_markdown_contains_every_runtime_contract() -> None:
    timeline = TimelineAnalysis(
        system="Jenkins",
        source_ticket_count=200,
        eras=[
            EraSummary(
                id="vm",
                label="VM ERA",
                period="2025",
                architecture="VM",
                dominant_resolution="SSH",
                valid_tools=["ssh", "systemctl"],
                retired_actions=["VM default"],
                ticket_count=80,
                current=False,
            ),
            EraSummary(
                id="helm",
                label="HELM ERA",
                period="2025",
                architecture="Helm",
                dominant_resolution="Helm",
                valid_tools=["helm"],
                retired_actions=["direct Helm"],
                ticket_count=55,
                current=False,
            ),
            EraSummary(
                id="gitops",
                label="GITOPS ERA",
                period="2026",
                architecture="GitOps",
                dominant_resolution="Git",
                valid_tools=["git", "argocd"],
                retired_actions=["kubectl"],
                ticket_count=40,
                current=False,
            ),
            EraSummary(
                id="ephemeral",
                label="CURRENT ERA",
                period="2026",
                architecture="GKE",
                dominant_resolution="JCasC",
                valid_tools=["gke", "git", "argocd"],
                retired_actions=[],
                ticket_count=25,
                current=True,
            ),
        ],
        current_era="ephemeral",
        legacy_exceptions=legacy_exceptions(),
        key_finding="Migration evidence wins.",
    )
    skill = TemporalSkill(
        name="jenkins-current-recovery",
        version="v4",
        current_era="ephemeral",
        current_architecture="Ephemeral GKE agents with JCasC and Argo CD",
        source_ticket_count=200,
        workflow=[
            SkillStep(id="inspect", tool="gke.inspect", instruction="Inspect pods."),
            SkillStep(id="edit", tool="git.pull-request", instruction="Update JCasC."),
            SkillStep(id="validate", tool="jcasc.validate", instruction="Validate."),
            SkillStep(id="diff", tool="argocd.diff", instruction="Inspect diff."),
        ],
        deprecated_actions=["VM restart", "direct Helm", "direct kubectl"],
        legacy_exceptions=legacy_exceptions(),
        temporal_rules=["current", "migration", "exact"],
        success_criteria=["pods ready", "diff approved", "no stale action"],
    )
    incident = IncidentAnalysis(
        incident="Queued builds",
        stale_majority_answer="Restart VM",
        stale_reason="Retired",
        current_recommendation="Update JCasC through Git.",
        planned_tool_trace=["gke", "git", "argocd"],
        jcasc_patch=(
            "serviceAccount: jenkins-agent\n"
            "value: jenkins-agent@gcp-project.iam.gserviceaccount.com"
        ),
    )
    report = TemporalReplayReport(checks={"safe": True}, score=100, verdict="PASS")
    content = render_skill_markdown(timeline, skill, incident, report)
    for required in [
        "# Jenkins Current Recovery",
        "## Routing policy",
        "jenkins-paris",
        "jenkins-barcelona",
        "jenkins-NYC",
        "## Current workflow",
        "## Deprecated by default",
        "## JCasC patch template",
        "replay_score: 100",
    ]:
        assert required in content
    assert "gcp-project" not in content
