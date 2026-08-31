"""Deterministic replay runtime for generated multi-domain skills."""

from app.catalog import definition
from app.models import Decision, ReplayCase, ReplayReport, SkillSpec, Ticket


def _matching_policy(skill: SkillSpec, terms: list[str]) -> Decision | None:
    for outcome in ("DENY", "ESCALATE", "RESOLVE"):
        for rule in skill.policy_rules:
            text = f"{rule.id} {rule.condition} {rule.rationale}".lower()
            if rule.outcome == outcome and all(term.lower() in text for term in terms):
                return rule.outcome
    return None


def execute_skill(skill: SkillSpec, ticket: Ticket) -> ReplayCase:
    """Execute policy decisions without using evaluation labels as runtime input."""

    config = definition(ticket.category)
    if ticket.required_policy_terms:
        actual = _matching_policy(skill, ticket.required_policy_terms) or "RESOLVE"
    else:
        actual = "RESOLVE"

    verification = [step.tool for step in config.workflow[:2]]
    if actual == "RESOLVE":
        trace = [step.tool for step in config.workflow]
        finding = "Standard work completed and an auditable business artifact was created."
    elif actual == "ESCALATE":
        trace = [*verification, config.escalation_tool, "audit.record"]
        finding = "Policy exception routed for approval before a privileged action."
    else:
        trace = [*verification, "audit.record"]
        finding = "Unsafe request denied before a privileged action."

    trace = list(dict.fromkeys(trace))
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
