"""Synthetic ticket dataset created for the hackathon demo."""

import json
from functools import lru_cache
from pathlib import Path

from app.models import Ticket


@lru_cache(maxsize=1)
def load_tickets() -> list[Ticket]:
    path = Path(__file__).parent.parent / "data" / "tickets.json"
    return [Ticket.model_validate(item) for item in json.loads(path.read_text())]


def tickets_for(split: str) -> list[Ticket]:
    return [ticket for ticket in load_tickets() if ticket.split == split]
