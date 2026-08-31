"""Gemini 3.5 agents that compile and repair enterprise skills."""

import json
import os
from typing import Any

from google import genai
from google.genai import types

from app.models import ReplayReport, SkillSpec, Ticket

MODEL = os.environ.get("TICKET2SKILL_MODEL", "gemini-3.5-flash")
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "ticket2skill-agentic-26")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")


class SkillAgents:
    """Structured Gemini agents with deterministic input and output contracts."""

    def __init__(self) -> None:
        self.client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)

    def _generate(self, prompt: str) -> SkillSpec:
        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=4096,
                response_mime_type="application/json",
                response_schema=SkillSpec,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned no structured skill")
        return SkillSpec.model_validate_json(response.text)

    def discover_skill(self, tickets: list[Ticket]) -> SkillSpec:
        evidence = [
            {
                "id": ticket.id,
                "issue": ticket.issue,
                "resolution_notes": ticket.resolution_notes,
                "requester_type": ticket.requester_type,
                "employment_status": ticket.employment_status,
            }
            for ticket in tickets
        ]
        prompt = f"""
You are Pattern Miner and Skill Builder agents working as one pipeline.
Compile the repeated human workflow in these resolved enterprise VPN tickets into a reusable skill.
Return SkillSpec JSON only. Set name to vpn-access-recovery and version to v1.
Use only these tools when evidenced: identity.lookup, employment.verify,
vpn.revoke_sessions, vpn.issue_recovery, audit.record.
Create a workflow that verifies identity and employment before issuing recovery.
Create policy rules only for conditions explicitly evidenced by the supplied tickets.
Do not invent policies for requester types or employment states absent from the evidence.

Resolved ticket evidence:
{json.dumps(evidence, indent=2)}
"""
        return self._generate(prompt)

    def repair_skill(self, skill: SkillSpec, report: ReplayReport) -> SkillSpec:
        failures: list[dict[str, Any]] = [
            {
                "ticket_id": case.ticket_id,
                "expected": case.expected,
                "actual": case.actual,
                "finding": case.finding,
            }
            for case in report.cases
            if not case.passed
        ]
        prompt = f"""
You are the Replay Critic agent. Repair this generated enterprise skill using held-out
regression failures. Return a complete SkillSpec JSON only.

Requirements:
- Keep name vpn-access-recovery and set version to v2.
- Preserve the successful active-employee recovery workflow.
- Add a policy whose condition contains contractor and manager approval; its outcome must be
  ESCALATE when approval is absent.
- Add a policy whose condition contains terminated; its outcome must be DENY.
- Add manager.request_approval to allowed_tools and workflow.
- Keep employment verification before any credential mutation.

Skill v1:
{skill.model_dump_json(indent=2)}

Held-out replay failures:
{json.dumps(failures, indent=2)}
"""
        return self._generate(prompt)
