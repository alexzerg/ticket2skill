"""Gemini 3.5 agents that compile and repair enterprise skills."""

import json
import os

from google import genai
from google.genai import types

from app.catalog import definition
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

    def discover_skill(self, category: str, tickets: list[Ticket]) -> SkillSpec:
        """Compile repeated human work from one evidence category."""

        config = definition(category)
        evidence = [
            {
                "id": ticket.id,
                "issue": ticket.issue,
                "resolution": ticket.resolution_notes,
                "attributes": ticket.attributes,
            }
            for ticket in tickets
        ]
        prompt = f"""
You are Pattern Miner and Skill Builder agents working as an autonomous compiler.
Analyze every resolved enterprise ticket below and compile the repeated human workflow into a
reusable agent skill. Return SkillSpec JSON only.

Required identity:
- name: {config.skill_name}
- category: {category}
- version: v1
- purpose: {config.purpose}
- inputs: {json.dumps(config.inputs)}

Only select tools from this evidence-bound allowlist:
{json.dumps(config.standard_tools)}

Create an ordered workflow, success criteria, and only policies explicitly evidenced by the solved
tickets. Do not invent exception policies for situations absent from the evidence.

Resolved evidence ({len(evidence)} tickets):
{json.dumps(evidence, separators=(",", ":"))}
"""
        generated = self._generate(prompt)
        return generated.model_copy(
            update={
                "name": config.skill_name,
                "category": category,
                "version": "v1",
                "policy_rules": [
                    rule for rule in generated.policy_rules if rule.outcome == "RESOLVE"
                ],
            }
        )

    def repair_skill(
        self,
        category: str,
        skill: SkillSpec,
        report: ReplayReport,
        held_out: list[Ticket],
    ) -> SkillSpec:
        """Use held-out regression evidence to compile the next version."""

        config = definition(category)
        failed_ids = {case.ticket_id for case in report.cases if not case.passed}
        failures = [
            {
                "ticket_id": ticket.id,
                "issue": ticket.issue,
                "attributes": ticket.attributes,
                "expected_outcome": ticket.expected_outcome,
                "required_policy_terms": ticket.required_policy_terms,
            }
            for ticket in held_out
            if ticket.id in failed_ids
        ]
        allowed_tools = [*config.standard_tools, config.escalation_tool]
        prompt = f"""
You are the Replay Critic agent. Repair the generated skill using only the held-out regression
failures. Return a complete SkillSpec JSON only.

Required identity:
- name: {config.skill_name}
- category: {category}
- version: v2

Preserve the successful standard workflow. Add policy rules for every failed case. Each policy
condition must contain all required_policy_terms from that failure and use its expected_outcome.
Add the category escalation tool when an ESCALATE policy needs it.
Allowed tools: {json.dumps(allowed_tools)}

Skill v1:
{skill.model_dump_json()}

Held-out failures:
{json.dumps(failures, separators=(",", ":"))}
"""
        generated = self._generate(prompt)
        return generated.model_copy(
            update={
                "name": config.skill_name,
                "category": category,
                "version": "v2",
            }
        )
