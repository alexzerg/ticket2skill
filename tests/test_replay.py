"""Deterministic replay and publication-gate tests."""

from app.data import tickets_for
from app.models import PolicyRule, SkillSpec, ToolStep
from app.replay import execute_skill, replay_skill


def skill(version: str, with_exception_policies: bool) -> SkillSpec:
    policies = [
        PolicyRule(
            id="active-employee",
            condition="requester is an active employee",
            outcome="RESOLVE",
            rationale="Resolved-ticket evidence supports standard recovery.",
        )
    ]
    tools = [
        "identity.lookup",
        "employment.verify",
        "vpn.revoke_sessions",
        "vpn.issue_recovery",
        "audit.record",
    ]
    if with_exception_policies:
        policies.extend(
            [
                PolicyRule(
                    id="contractor-approval",
                    condition="contractor requires manager approval when approval is absent",
                    outcome="ESCALATE",
                    rationale="Held-out policy evidence requires human approval.",
                ),
                PolicyRule(
                    id="terminated-deny",
                    condition="terminated identities are denied",
                    outcome="DENY",
                    rationale="Terminated users cannot receive credentials.",
                ),
            ]
        )
        tools.append("manager.request_approval")
    return SkillSpec(
        name="vpn-access-recovery",
        version=version,
        purpose="Recover VPN access safely.",
        inputs=["identity", "employment_status", "requester_type"],
        allowed_tools=tools,
        workflow=[
            ToolStep(id="lookup", tool="identity.lookup", instruction="Find identity."),
            ToolStep(id="verify", tool="employment.verify", instruction="Verify status."),
            ToolStep(id="revoke", tool="vpn.revoke_sessions", instruction="Revoke sessions."),
        ],
        policy_rules=policies,
        success_criteria=["Correct outcome", "Authorized tool trace"],
    )


def test_v1_exposes_unseen_enterprise_policy_failures() -> None:
    report = replay_skill(skill("v1", False), tickets_for("held_out"))
    assert report.score == 50
    assert report.verdict == "FAIL"
    assert {case.ticket_id for case in report.cases if not case.passed} == {
        "INC-2002",
        "INC-2004",
    }


def test_v2_passes_held_out_replay_and_new_ticket_queue() -> None:
    generated = skill("v2", True)
    report = replay_skill(generated, tickets_for("held_out"))
    new_results = {
        ticket.id: execute_skill(generated, ticket) for ticket in tickets_for("new")
    }
    assert report.score == 100
    assert report.verdict == "PASS"
    assert new_results["INC-3001"].actual == "RESOLVE"
    assert new_results["INC-3002"].actual == "ESCALATE"
    assert "manager.request_approval" in new_results["INC-3002"].tool_trace
    assert "vpn.issue_recovery" not in new_results["INC-3002"].tool_trace
    assert new_results["INC-3003"].actual == "DENY"
    assert "vpn.issue_recovery" not in new_results["INC-3003"].tool_trace
