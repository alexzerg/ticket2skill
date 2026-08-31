"""Deterministic routing for published temporal Jenkins skills."""

from app.models import ControllerRouteDecision, TemporalSkill


def route_controller(controller: str, skill: TemporalSkill) -> ControllerRouteDecision:
    """Route an incident using the generated skill's exact legacy allowlist."""

    exception = next(
        (item for item in skill.legacy_exceptions if item.controller == controller),
        None,
    )
    if exception is not None:
        return ControllerRouteDecision(
            controller=controller,
            route="legacy_vm_exception",
            status="CONTROLLED_EXCEPTION",
            exact_match=True,
            architecture=exception.architecture,
            reason=(
                f"{controller} exactly matches the published legacy allowlist. "
                "The VM runbook is valid only for this controller."
            ),
            actions=[
                *exception.allowed_actions,
                "Do not reuse this route for another Jenkins controller.",
            ],
        )

    allowlist = ", ".join(item.controller for item in skill.legacy_exceptions)
    return ControllerRouteDecision(
        controller=controller,
        route="current_gke_gitops",
        status="CURRENT_DEFAULT",
        exact_match=False,
        architecture=skill.current_architecture,
        reason=(
            f"{controller} is not an exact match for the legacy allowlist ({allowlist}). "
            "The current GKE/GitOps architecture takes precedence."
        ),
        actions=[f"{step.tool}: {step.instruction}" for step in skill.workflow],
    )
