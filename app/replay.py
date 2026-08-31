"""Deterministic replay runtime for generated skills."""

from typing import Literal

from app.models import ReplayCase, ReplayReport, SkillSpec, Ticket


def _policy_text(skill: SkillSpec, outcome: str) -> str:
    return " ".join(
        f"{rule.id} {rule.condition} {rule.rationale}".lower()
        for rule in skill.policy_rules
        if rule.outcome == outcome
    )


def execute_skill(skill: SkillSpec, ticket: Ticket) -> ReplayCase:
    """Execute policy decisions and emit an auditable tool trajectory."""

    deny_policy = _policy_text(skill, "DENY")
    escalate_policy = _policy_text(skill, "ESCALATE")
    trace = ["identity.lookup", "employment.verify"]
    actual: Literal["RESOLVE", "ESCALATE", "DENY"]

    if ticket.employment_status == "terminated" and "terminated" in deny_policy:
        actual = "DENY"
        trace.append("audit.record")
        finding = "Terminated identity denied before credential mutation."
    elif (
        ticket.requester_type == "contractor"
        and not ticket.manager_approval
        and "contractor" in escalate_policy
        and "approval" in escalate_policy
    ):
        actual = "ESCALATE"
        trace.extend(["manager.request_approval", "audit.record"])
        finding = "Contractor recovery paused for manager approval."
    else:
        actual = "RESOLVE"
        trace.extend(["vpn.revoke_sessions", "vpn.issue_recovery", "audit.record"])
        finding = "Standard verified recovery workflow executed."

    unauthorized = [tool for tool in trace if tool not in skill.allowed_tools]
    passed = actual == ticket.expected_outcome and not unauthorized
    if unauthorized:
        finding = f"Unauthorized tool trajectory: {', '.join(unauthorized)}"

    return ReplayCase(
        ticket_id=ticket.id,
        expected=ticket.expected_outcome,
        actual=actual,
        passed=passed,
        tool_trace=trace,
        finding=finding,
    )


def replay_skill(skill: SkillSpec, tickets: list[Ticket]) -> ReplayReport:
    cases = [execute_skill(skill, ticket) for ticket in tickets]
    passed = sum(case.passed for case in cases)
    total = len(cases)
    score = round(passed / total * 100) if total else 0
    failures = [f"{case.ticket_id}: {case.finding}" for case in cases if not case.passed]
    return ReplayReport(
        skill_name=skill.name,
        skill_version=skill.version,
        passed=passed,
        total=total,
        score=score,
        cases=cases,
        failures=failures,
        verdict="PASS" if score == 100 else "FAIL",
    )
