"""Interactive Skill Router tests."""

import pytest

from app.data import LEGACY_JENKINS_INSTANCES, legacy_exceptions
from app.models import SkillStep, TemporalSkill
from app.routing import route_controller


def skill() -> TemporalSkill:
    return TemporalSkill(
        name="jenkins-current-recovery",
        version="v4",
        current_era="ephemeral",
        current_architecture="Ephemeral GKE agents managed through JCasC and Argo CD",
        source_ticket_count=200,
        workflow=[
            SkillStep(id="inspect", tool="gke.inspect", instruction="Inspect agent pods."),
            SkillStep(id="edit", tool="git.pull-request", instruction="Update JCasC."),
            SkillStep(id="validate", tool="jcasc.validate", instruction="Validate JCasC."),
            SkillStep(id="diff", tool="argocd.diff", instruction="Inspect the diff."),
        ],
        deprecated_actions=["default VM restart", "direct Helm", "direct kubectl"],
        legacy_exceptions=legacy_exceptions(),
        temporal_rules=["Use current era", "Respect migrations", "Use exact exceptions"],
        success_criteria=["Agent ready", "Diff approved", "No stale action"],
    )


@pytest.mark.parametrize("controller", LEGACY_JENKINS_INSTANCES)
def test_exact_legacy_controller_uses_scoped_vm_route(controller: str) -> None:
    decision = route_controller(controller, skill())
    assert decision.route == "legacy_vm_exception"
    assert decision.status == "CONTROLLED_EXCEPTION"
    assert decision.exact_match
    assert "systemctl" in " ".join(decision.actions)


def test_non_allowlisted_controller_uses_current_route() -> None:
    decision = route_controller("jenkins-london", skill())
    assert decision.route == "current_gke_gitops"
    assert decision.status == "CURRENT_DEFAULT"
    assert not decision.exact_match
    assert decision.actions[0].startswith("gke.inspect:")


def test_legacy_matching_is_case_sensitive() -> None:
    decision = route_controller("jenkins-nyc", skill())
    assert decision.route == "current_gke_gitops"
    assert not decision.exact_match
