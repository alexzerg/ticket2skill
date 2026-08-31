"""Multi-domain dataset and deterministic replay tests."""

from app.catalog import CATEGORIES, definition
from app.data import held_out_tickets, new_tickets, training_tickets
from app.models import PolicyRule, SkillSpec
from app.replay import execute_skill, replay_skill

EXPECTED_COUNTS = {
    "vpn": 200,
    "jenkins": 120,
    "hardware": 80,
    "database": 40,
    "sonarqube": 30,
}


def skill(category: str, version: str, repaired: bool) -> SkillSpec:
    config = definition(category)
    policies: list[PolicyRule] = []
    if repaired:
        policies = [
            PolicyRule(
                id=f"policy-{index}",
                condition=" and ".join(ticket.required_policy_terms),
                outcome=ticket.expected_outcome,
                rationale=f"Held-out failure evidence from {ticket.id}.",
            )
            for index, ticket in enumerate(held_out_tickets(category), start=1)
            if ticket.required_policy_terms
        ]
    return SkillSpec(
        name=config.skill_name,
        category=category,
        version=version,
        purpose=config.purpose,
        inputs=config.inputs,
        allowed_tools=[*config.standard_tools, config.escalation_tool],
        workflow=config.workflow,
        policy_rules=policies,
        success_criteria=["Correct business outcome", "Authorized tool trajectory"],
    )


def test_ticket_evidence_counts_are_distinct_and_exact() -> None:
    assert set(CATEGORIES) == set(EXPECTED_COUNTS)
    assert {category: len(training_tickets(category)) for category in CATEGORIES} == EXPECTED_COUNTS
    assert sum(EXPECTED_COUNTS.values()) == 470


def test_v1_exposes_unseen_policy_failures_in_every_category() -> None:
    for category in CATEGORIES:
        report = replay_skill(skill(category, "v1", False), held_out_tickets(category))
        assert report.verdict == "FAIL"
        assert report.score < 100
        assert report.failures


def test_repaired_skills_pass_and_process_new_work() -> None:
    for category in CATEGORIES:
        generated = skill(category, "v2", True)
        report = replay_skill(generated, held_out_tickets(category))
        outcomes = {execute_skill(generated, ticket).actual for ticket in new_tickets(category)}
        assert report.score == 100
        assert report.verdict == "PASS"
        assert outcomes == {"RESOLVE", "ESCALATE", "DENY"}
