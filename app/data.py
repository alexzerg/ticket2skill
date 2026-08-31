"""Synthetic Jenkins operations history spanning four architecture eras."""

from datetime import date, timedelta
from functools import lru_cache
from typing import TypedDict

from app.models import (
    DriftEvent,
    EraId,
    JenkinsTicket,
    LegacyException,
    MigrationEvent,
)

LEGACY_JENKINS_INSTANCES = ("jenkins-paris", "jenkins-barcelona", "jenkins-NYC")


class EraConfig(TypedDict):
    count: int
    start: date
    architecture: str
    resolutions: list[str]
    tools: list[str]


ERA_CONFIG: dict[EraId, EraConfig] = {
    "vm": {
        "count": 80,
        "start": date(2025, 9, 1),
        "architecture": (
            "40 independent Jenkins controllers on Compute Engine VMs; 37 were retired and "
            "three remain as controlled legacy exceptions"
        ),
        "resolutions": [
            (
                "SSH to the affected VM, inspect journalctl, restart Jenkins with "
                "systemctl, and edit local configuration if required."
            ),
            (
                "Connect to the Compute Engine instance, clean the local workspace, "
                "restart the Jenkins service, and verify the node manually."
            ),
        ],
        "tools": ["gcloud.compute.ssh", "journalctl", "systemctl", "local-config-edit"],
    },
    "helm": {
        "count": 55,
        "start": date(2025, 12, 1),
        "architecture": "Jenkins consolidated on Google Kubernetes Engine and installed with Helm",
        "resolutions": [
            (
                "Inspect controller and agent pods, update Helm values, run helm upgrade, "
                "and verify the Kubernetes rollout."
            ),
            (
                "Read GKE pod logs, adjust the Jenkins Helm release values, upgrade the "
                "release, and confirm agents reconnect."
            ),
        ],
        "tools": ["kubectl.logs", "helm.values", "helm.upgrade", "kubectl.rollout"],
    },
    "gitops": {
        "count": 40,
        "start": date(2026, 5, 1),
        "architecture": "Jenkins Configuration as Code stored in Git and reconciled by Argo CD",
        "resolutions": [
            (
                "Update the JCasC file in Git, open a pull request, inspect the Argo CD "
                "diff, and sync after approval."
            ),
            (
                "Diagnose the controller, patch JCasC or Helm values through Git, "
                "validate the pull request, and let Argo CD reconcile."
            ),
        ],
        "tools": ["git.pull_request", "jcasc.validate", "argocd.diff", "argocd.sync"],
    },
    "ephemeral": {
        "count": 25,
        "start": date(2026, 8, 1),
        "architecture": "Argo CD managed JCasC with ephemeral GKE agents and Workload Identity",
        "resolutions": [
            (
                "Inspect the Kubernetes agent pod template and Workload Identity binding, "
                "patch JCasC in Git, validate Argo CD diff, and reconcile."
            ),
            (
                "Check ephemeral agent scheduling and service account bindings, update the "
                "JCasC pod template by pull request, and verify Argo CD health."
            ),
        ],
        "tools": [
            "gke.agent-diagnostics",
            "workload-identity.inspect",
            "git.pull_request",
            "jcasc.validate",
            "argocd.diff",
            "argocd.sync",
        ],
    },
}

ISSUES = [
    "Build queue is growing because Jenkins agents are offline",
    "Pipeline executors disappeared after a configuration change",
    "Build jobs remain queued with no matching agent",
    "Jenkins controller reports disconnected build workers",
    "CI throughput dropped after agent provisioning failed",
    "Release pipelines cannot acquire an executor",
    "Build agents fail during startup and reconnect repeatedly",
    "Jenkins jobs are blocked after credentials rotation",
]

CURRENT_INCIDENT = (
    "Thirty-seven Jenkins builds are queued. Ephemeral GKE agents fail to start after a service "
    "account change. The controller is healthy, but new agent pods cannot authenticate."
)

NEXT_DRIFT_EVENT = DriftEvent(
    event_id="ARCH-2026-09-WIF",
    effective_date="2026-09-01",
    source="gcp",
    title="Jenkins agents adopt direct Workload Identity Federation principal binding",
    change=(
        "The ci-build-agent Kubernetes service account now receives IAM permissions directly "
        "through its workload identity principal. Google service account impersonation is retired."
    ),
    retired_configuration="iam.gke.io/gcp-service-account annotation on jenkins-agent",
    new_configuration=(
        "ci-build-agent Kubernetes service account with direct principalSet IAM binding managed "
        "through Terraform and GitOps"
    ),
)


def legacy_exceptions() -> list[LegacyException]:
    """Return the exact legacy allowlist that survives the VM-to-GKE migration."""

    architecture = "Dedicated Jenkins controller on a retained Compute Engine VM"
    allowed_actions = [
        "SSH to the named Compute Engine VM and inspect journalctl.",
        "Restart only the named Jenkins service with systemctl after diagnosis.",
    ]
    return [
        LegacyException(
            controller="jenkins-paris",
            era="vm",
            architecture=architecture,
            routing_condition=(
                "Use only when the incident target exactly matches jenkins-paris."
            ),
            allowed_actions=allowed_actions,
        ),
        LegacyException(
            controller="jenkins-barcelona",
            era="vm",
            architecture=architecture,
            routing_condition=(
                "Use only when the incident target exactly matches jenkins-barcelona."
            ),
            allowed_actions=allowed_actions,
        ),
        LegacyException(
            controller="jenkins-NYC",
            era="vm",
            architecture=architecture,
            routing_condition="Use only when the incident target exactly matches jenkins-NYC.",
            allowed_actions=allowed_actions,
        ),
    ]


@lru_cache(maxsize=1)
def load_tickets() -> list[JenkinsTicket]:
    tickets: list[JenkinsTicket] = []
    sequence = 1
    for era, config in ERA_CONFIG.items():
        count = int(config["count"])
        start = config["start"]
        for index in range(count):
            resolved_at = start + timedelta(days=index * 2)
            resolutions = config["resolutions"]
            legacy_target = (
                LEGACY_JENKINS_INSTANCES[index]
                if era == "vm" and index < len(LEGACY_JENKINS_INSTANCES)
                else "shared-fleet"
            )
            tickets.append(
                JenkinsTicket(
                    id=f"OPS-{1000 + sequence}",
                    resolved_at=resolved_at.isoformat(),
                    era=era,
                    architecture=str(config["architecture"]),
                    issue=(
                        f"{ISSUES[index % len(ISSUES)]}; "
                        f"team={['Payments', 'Platform', 'Data', 'Risk'][index % 4]}; "
                        f"priority={['medium', 'high', 'critical'][index % 3]}; "
                        f"controller={legacy_target}"
                    ),
                    resolution=resolutions[index % len(resolutions)],
                    tools_used=list(config["tools"]),
                )
            )
            sequence += 1
    return tickets


def migration_events() -> list[MigrationEvent]:
    return [
        MigrationEvent(
            effective_date="2025-12-01",
            from_architecture="40 Compute Engine VM controllers",
            to_architecture="Consolidated GKE deployment managed by Helm",
            policy_change=(
                "SSH and systemctl recovery procedures are retired by default. They remain valid "
                "only for jenkins-paris, jenkins-barcelona, and jenkins-NYC."
            ),
        ),
        MigrationEvent(
            effective_date="2026-05-01",
            from_architecture="Direct Helm administration",
            to_architecture="JCasC and Helm values reconciled by Argo CD",
            policy_change=(
                "Persistent kubectl and Helm mutations are forbidden; Git is source of truth."
            ),
        ),
        MigrationEvent(
            effective_date="2026-08-01",
            from_architecture="Static Kubernetes build agents",
            to_architecture="Ephemeral GKE agents using Workload Identity",
            policy_change=(
                "Static-node restart advice is retired; agent templates and identity "
                "bindings are managed through JCasC."
            ),
        ),
    ]
