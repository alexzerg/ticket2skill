"""Temporal skill lifecycle transitions."""

from app.models import DriftUpdate, IncidentAnalysis, TemporalSkill


def _deduplicate(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def apply_drift_update(
    previous: TemporalSkill,
    incident: IncidentAnalysis,
    update: DriftUpdate,
) -> tuple[TemporalSkill, IncidentAnalysis]:
    """Create an immutable v5 skill and incident result from a validated drift update."""
    if previous.version != update.previous_version:
        raise ValueError("drift update does not match the current skill version")
    skill = TemporalSkill(
        name=previous.name,
        version=update.new_version,
        supersedes=previous.version,
        architecture_event=update.event_id,
        current_era=previous.current_era,
        current_architecture=update.current_architecture,
        source_ticket_count=previous.source_ticket_count,
        workflow=update.workflow,
        deprecated_actions=_deduplicate([*previous.deprecated_actions, *update.retired_actions]),
        legacy_exceptions=update.preserved_legacy_exceptions,
        temporal_rules=_deduplicate(
            [
                *previous.temporal_rules,
                f"Architecture event {update.event_id} supersedes {previous.version}.",
                "Use direct Workload Identity Federation principal binding for GKE agents.",
            ]
        ),
        success_criteria=[
            "Ephemeral GKE agents launch as ci-build-agent and authenticate directly.",
            "Terraform IAM and JCasC changes are validated before Argo CD sync.",
            "The three exact VM exceptions remain isolated from GKE recovery.",
        ],
    )
    updated_incident = incident.model_copy(
        update={
            "current_recommendation": " ".join(step.instruction for step in update.workflow),
            "planned_tool_trace": [step.tool for step in update.workflow],
            "jcasc_patch": update.jcasc_patch,
        }
    )
    return skill, updated_incident
