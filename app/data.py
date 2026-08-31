"""Deterministic synthetic multi-domain enterprise ticket datasets."""

from functools import lru_cache

from app.catalog import CATEGORIES, definition, materialize_cases
from app.models import CategorySummary, Ticket

TEAMS = ["Payments", "Treasury", "Platform", "Data", "Security", "Support", "Finance", "Risk"]
REGIONS = ["New York", "London", "Paris", "Singapore", "Toronto", "Austin", "Berlin", "Sydney"]


@lru_cache(maxsize=8)
def training_tickets(category: str) -> list[Ticket]:
    config = definition(category)
    tickets: list[Ticket] = []
    for index in range(config.evidence_count):
        team = TEAMS[index % len(TEAMS)]
        region = REGIONS[(index * 3) % len(REGIONS)]
        attributes = {
            **config.standard_attributes,
            "team": team,
            "region": region,
            "priority": ["low", "medium", "high"][index % 3],
            "previous_attempts": index % 3,
        }
        issue = config.issue_templates[index % len(config.issue_templates)]
        resolution = config.resolution_templates[index % len(config.resolution_templates)]
        tickets.append(
            Ticket(
                id=f"{category.upper()}-R{index + 1:04d}",
                category=category,
                split="training",
                issue=f"{issue} for {team} in {region}",
                resolution_notes=f"{resolution} Resolution time: {8 + index % 19} minutes.",
                attributes=attributes,
                expected_outcome="RESOLVE",
            )
        )
    return tickets


@lru_cache(maxsize=8)
def held_out_tickets(category: str) -> list[Ticket]:
    config = definition(category)
    return materialize_cases(category, "held_out", config.held_out)


@lru_cache(maxsize=8)
def new_tickets(category: str) -> list[Ticket]:
    config = definition(category)
    return materialize_cases(category, "new", config.new_cases)


def category_summaries() -> list[CategorySummary]:
    return [
        CategorySummary(
            id=config.id,
            name=config.name,
            description=config.description,
            evidence_count=config.evidence_count,
            held_out_count=len(config.held_out),
            new_count=len(config.new_cases),
        )
        for config in CATEGORIES.values()
    ]
