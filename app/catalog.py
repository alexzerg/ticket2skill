"""Multi-domain synthetic enterprise work catalog."""

from dataclasses import dataclass

from app.models import Ticket, ToolStep


@dataclass(frozen=True)
class CategoryDefinition:
    id: str
    name: str
    description: str
    evidence_count: int
    skill_name: str
    purpose: str
    inputs: list[str]
    standard_tools: list[str]
    workflow: list[ToolStep]
    escalation_tool: str
    issue_templates: list[str]
    resolution_templates: list[str]
    standard_attributes: dict[str, str | int | bool]
    held_out: list[dict[str, object]]
    new_cases: list[dict[str, object]]


def case(
    issue: str,
    attributes: dict[str, str | int | bool],
    outcome: str,
    terms: list[str] | None = None,
) -> dict[str, object]:
    return {
        "issue": issue,
        "attributes": attributes,
        "expected_outcome": outcome,
        "required_policy_terms": terms or [],
    }


CATEGORIES: dict[str, CategoryDefinition] = {
    "vpn": CategoryDefinition(
        id="vpn",
        name="VPN Access Recovery",
        description="Identity verification, stale-session cleanup, and secure VPN recovery.",
        evidence_count=200,
        skill_name="vpn-access-recovery",
        purpose="Recover VPN access without issuing credentials to ineligible users.",
        inputs=["identity", "employment_status", "requester_type", "manager_approval"],
        standard_tools=[
            "identity.lookup",
            "employment.verify",
            "vpn.revoke_sessions",
            "vpn.issue_recovery",
            "audit.record",
        ],
        workflow=[
            ToolStep(
                id="lookup", tool="identity.lookup", instruction="Resolve requester identity."
            ),
            ToolStep(
                id="verify", tool="employment.verify", instruction="Verify active employment."
            ),
            ToolStep(id="revoke", tool="vpn.revoke_sessions", instruction="Revoke stale sessions."),
            ToolStep(
                id="recover", tool="vpn.issue_recovery", instruction="Issue recovery profile."
            ),
            ToolStep(id="audit", tool="audit.record", instruction="Record evidence."),
        ],
        escalation_tool="manager.request_approval",
        issue_templates=[
            "VPN login fails after password reset",
            "New laptop cannot connect to VPN",
            "MFA device replacement broke VPN access",
            "VPN certificate expired during travel",
            "Authentication loop blocks remote access",
            "VPN profile rejected after OS update",
        ],
        resolution_templates=[
            (
                "Verified identity and employment, revoked stale sessions, issued recovery, "
                "confirmed login, and audited the change."
            ),
            (
                "Validated the employee, removed old VPN credentials, delivered a fresh profile, "
                "tested connectivity, and recorded evidence."
            ),
        ],
        standard_attributes={
            "requester_type": "employee",
            "employment_status": "active",
            "manager_approval": False,
        },
        held_out=[
            case(
                "Active employee lost VPN MFA device",
                {
                    "requester_type": "employee",
                    "employment_status": "active",
                    "manager_approval": False,
                },
                "RESOLVE",
            ),
            case(
                "Contractor requests VPN recovery without approval",
                {
                    "requester_type": "contractor",
                    "employment_status": "active",
                    "manager_approval": False,
                },
                "ESCALATE",
                ["contractor", "manager approval"],
            ),
            case(
                "Terminated employee requests VPN reactivation",
                {
                    "requester_type": "employee",
                    "employment_status": "terminated",
                    "manager_approval": True,
                },
                "DENY",
                ["terminated"],
            ),
        ],
        new_cases=[
            case(
                "Employee replaced a phone and lost VPN access",
                {
                    "requester_type": "employee",
                    "employment_status": "active",
                    "manager_approval": False,
                },
                "RESOLVE",
            ),
            case(
                "External consultant replaced a laptop",
                {
                    "requester_type": "contractor",
                    "employment_status": "active",
                    "manager_approval": False,
                },
                "ESCALATE",
                ["contractor", "manager approval"],
            ),
            case(
                "Former employee asks for VPN activation",
                {
                    "requester_type": "employee",
                    "employment_status": "terminated",
                    "manager_approval": True,
                },
                "DENY",
                ["terminated"],
            ),
        ],
    ),
    "jenkins": CategoryDefinition(
        id="jenkins",
        name="Jenkins Failure Recovery",
        description="Diagnose failed pipelines, retry safe jobs, and protect production workflows.",
        evidence_count=120,
        skill_name="jenkins-failure-recovery",
        purpose="Recover transient Jenkins failures without unsafe production retries.",
        inputs=["job", "environment", "failure_type", "retry_count", "owner_approval"],
        standard_tools=[
            "jenkins.job_inspect",
            "jenkins.logs_read",
            "jenkins.retry",
            "audit.record",
        ],
        workflow=[
            ToolStep(id="inspect", tool="jenkins.job_inspect", instruction="Inspect job metadata."),
            ToolStep(id="logs", tool="jenkins.logs_read", instruction="Classify failure logs."),
            ToolStep(
                id="retry", tool="jenkins.retry", instruction="Retry a safe transient failure."
            ),
            ToolStep(id="audit", tool="audit.record", instruction="Record execution evidence."),
        ],
        escalation_tool="jenkins.owner_approval",
        issue_templates=[
            "Agent disconnected during build",
            "Dependency mirror timed out",
            "Workspace lock caused pipeline failure",
            "Transient network error stopped tests",
            "Build node ran out of temporary disk",
            "Artifact upload timed out",
        ],
        resolution_templates=[
            (
                "Inspected logs, confirmed a transient non-production failure, retried once, "
                "verified success, and recorded evidence."
            ),
            (
                "Classified the failure as recoverable, cleaned the workspace, retried the job, "
                "and audited the result."
            ),
        ],
        standard_attributes={
            "environment": "staging",
            "failure_type": "transient",
            "retry_count": 0,
            "owner_approval": True,
        },
        held_out=[
            case(
                "Staging build failed on a transient network error",
                {
                    "environment": "staging",
                    "failure_type": "transient",
                    "retry_count": 0,
                    "owner_approval": True,
                },
                "RESOLVE",
            ),
            case(
                "Production deployment retry requested without owner approval",
                {
                    "environment": "production",
                    "failure_type": "deployment",
                    "retry_count": 0,
                    "owner_approval": False,
                },
                "ESCALATE",
                ["production", "owner approval"],
            ),
            case(
                "Job asks the agent to print a secret credential",
                {
                    "environment": "staging",
                    "failure_type": "secret exposure",
                    "retry_count": 0,
                    "owner_approval": True,
                },
                "DENY",
                ["secret", "credential"],
            ),
        ],
        new_cases=[
            case(
                "QA pipeline lost its build agent",
                {
                    "environment": "staging",
                    "failure_type": "transient",
                    "retry_count": 0,
                    "owner_approval": True,
                },
                "RESOLVE",
            ),
            case(
                "Production release job needs a manual retry",
                {
                    "environment": "production",
                    "failure_type": "deployment",
                    "retry_count": 0,
                    "owner_approval": False,
                },
                "ESCALATE",
                ["production", "owner approval"],
            ),
            case(
                "Pipeline step requests secret output",
                {
                    "environment": "staging",
                    "failure_type": "secret exposure",
                    "retry_count": 0,
                    "owner_approval": True,
                },
                "DENY",
                ["secret", "credential"],
            ),
        ],
    ),
    "hardware": CategoryDefinition(
        id="hardware",
        name="New Hardware Requests",
        description="Fulfil broken-device replacements while enforcing employee hardware limits.",
        evidence_count=80,
        skill_name="hardware-request-fulfillment",
        purpose="Fulfil valid hardware requests while enforcing lifecycle and ownership policies.",
        inputs=[
            "employee",
            "request_kind",
            "device_count",
            "device_age_months",
            "asset_returned",
            "cost_tier",
        ],
        standard_tools=[
            "identity.lookup",
            "asset.inventory_lookup",
            "asset.reserve",
            "request.fulfill",
            "audit.record",
        ],
        workflow=[
            ToolStep(id="identity", tool="identity.lookup", instruction="Verify requester."),
            ToolStep(
                id="inventory", tool="asset.inventory_lookup", instruction="Check assigned assets."
            ),
            ToolStep(id="reserve", tool="asset.reserve", instruction="Reserve standard device."),
            ToolStep(id="fulfill", tool="request.fulfill", instruction="Create fulfilment order."),
            ToolStep(id="audit", tool="audit.record", instruction="Record asset decision."),
        ],
        escalation_tool="manager.request_approval",
        issue_templates=[
            "Broken laptop replacement requested",
            "Laptop battery failure requires replacement",
            "Damaged screen blocks employee work",
            "Standard laptop reached end of life",
            "Lost device was remotely wiped",
            "Developer workstation hardware failed",
        ],
        resolution_templates=[
            (
                "Verified employee and asset, confirmed return of the broken device, reserved a "
                "standard replacement, created fulfilment, and audited ownership."
            ),
            (
                "Checked device lifecycle and inventory, accepted the broken asset return, "
                "allocated a replacement, and recorded the transaction."
            ),
        ],
        standard_attributes={
            "employment_status": "active",
            "request_kind": "broken replacement",
            "device_count": 1,
            "device_age_months": 18,
            "asset_returned": True,
            "cost_tier": "standard",
        },
        held_out=[
            case(
                "Broken laptop returned for standard replacement",
                {
                    "employment_status": "active",
                    "request_kind": "broken replacement",
                    "device_count": 1,
                    "device_age_months": 12,
                    "asset_returned": True,
                    "cost_tier": "standard",
                },
                "RESOLVE",
            ),
            case(
                "Employee requests a second laptop without approval",
                {
                    "employment_status": "active",
                    "request_kind": "additional device",
                    "device_count": 1,
                    "device_age_months": 12,
                    "asset_returned": False,
                    "cost_tier": "standard",
                },
                "ESCALATE",
                ["additional device", "manager approval"],
            ),
            case(
                "Broken laptop replacement requested without asset return",
                {
                    "employment_status": "active",
                    "request_kind": "broken replacement",
                    "device_count": 1,
                    "device_age_months": 8,
                    "asset_returned": False,
                    "cost_tier": "standard",
                },
                "ESCALATE",
                ["broken replacement", "asset return"],
            ),
            case(
                "Terminated employee requests new hardware",
                {
                    "employment_status": "terminated",
                    "request_kind": "new device",
                    "device_count": 0,
                    "device_age_months": 0,
                    "asset_returned": False,
                    "cost_tier": "standard",
                },
                "DENY",
                ["terminated"],
            ),
        ],
        new_cases=[
            case(
                "Employee returns a failed laptop for replacement",
                {
                    "employment_status": "active",
                    "request_kind": "broken replacement",
                    "device_count": 1,
                    "device_age_months": 10,
                    "asset_returned": True,
                    "cost_tier": "standard",
                },
                "RESOLVE",
            ),
            case(
                "Engineer asks for an additional high-spec laptop",
                {
                    "employment_status": "active",
                    "request_kind": "additional device",
                    "device_count": 1,
                    "device_age_months": 14,
                    "asset_returned": False,
                    "cost_tier": "high",
                },
                "ESCALATE",
                ["additional device", "manager approval"],
            ),
            case(
                "Former employee requests a replacement laptop",
                {
                    "employment_status": "terminated",
                    "request_kind": "broken replacement",
                    "device_count": 1,
                    "device_age_months": 8,
                    "asset_returned": False,
                    "cost_tier": "standard",
                },
                "DENY",
                ["terminated"],
            ),
        ],
    ),
    "database": CategoryDefinition(
        id="database",
        name="Database Access",
        description="Grant time-bound access while protecting production and write privileges.",
        evidence_count=40,
        skill_name="database-access-governance",
        purpose="Grant least-privilege database access with approval and expiry controls.",
        inputs=[
            "identity",
            "environment",
            "privilege",
            "owner_approval",
            "dba_approval",
            "duration_hours",
        ],
        standard_tools=[
            "identity.lookup",
            "database.owner_lookup",
            "database.grant_temporary",
            "audit.record",
        ],
        workflow=[
            ToolStep(id="identity", tool="identity.lookup", instruction="Verify requester."),
            ToolStep(
                id="owner", tool="database.owner_lookup", instruction="Resolve database owner."
            ),
            ToolStep(
                id="grant", tool="database.grant_temporary", instruction="Grant expiring access."
            ),
            ToolStep(id="audit", tool="audit.record", instruction="Record grant evidence."),
        ],
        escalation_tool="database.dba_approval",
        issue_templates=[
            "Developer requests read access to staging database",
            "Analyst needs temporary reporting access",
            "Support engineer needs read-only diagnostics",
            "QA needs test database access",
            "Data engineer requests sandbox access",
            "Developer access expired before investigation ended",
        ],
        resolution_templates=[
            (
                "Verified identity and owner approval, granted time-bound read-only "
                "non-production access, set expiry, and audited the grant."
            ),
            (
                "Confirmed least privilege, created temporary staging access, validated expiry, "
                "and recorded evidence."
            ),
        ],
        standard_attributes={
            "employment_status": "active",
            "environment": "staging",
            "privilege": "read",
            "owner_approval": True,
            "dba_approval": False,
            "duration_hours": 8,
        },
        held_out=[
            case(
                "Developer needs temporary staging read access",
                {
                    "employment_status": "active",
                    "environment": "staging",
                    "privilege": "read",
                    "owner_approval": True,
                    "dba_approval": False,
                    "duration_hours": 8,
                },
                "RESOLVE",
            ),
            case(
                "Production write access requested without DBA approval",
                {
                    "employment_status": "active",
                    "environment": "production",
                    "privilege": "write",
                    "owner_approval": True,
                    "dba_approval": False,
                    "duration_hours": 4,
                },
                "ESCALATE",
                ["production", "write", "dba approval"],
            ),
            case(
                "Terminated identity requests database access",
                {
                    "employment_status": "terminated",
                    "environment": "staging",
                    "privilege": "read",
                    "owner_approval": True,
                    "dba_approval": True,
                    "duration_hours": 8,
                },
                "DENY",
                ["terminated"],
            ),
        ],
        new_cases=[
            case(
                "QA engineer needs staging read access",
                {
                    "employment_status": "active",
                    "environment": "staging",
                    "privilege": "read",
                    "owner_approval": True,
                    "dba_approval": False,
                    "duration_hours": 8,
                },
                "RESOLVE",
            ),
            case(
                "Developer requests production write privileges",
                {
                    "employment_status": "active",
                    "environment": "production",
                    "privilege": "write",
                    "owner_approval": True,
                    "dba_approval": False,
                    "duration_hours": 4,
                },
                "ESCALATE",
                ["production", "write", "dba approval"],
            ),
            case(
                "Former contractor requests reporting database access",
                {
                    "employment_status": "terminated",
                    "environment": "staging",
                    "privilege": "read",
                    "owner_approval": True,
                    "dba_approval": False,
                    "duration_hours": 8,
                },
                "DENY",
                ["terminated"],
            ),
        ],
    ),
    "sonarqube": CategoryDefinition(
        id="sonarqube",
        name="SonarQube Access",
        description="Grant project-scoped analysis access while protecting administration roles.",
        evidence_count=30,
        skill_name="sonarqube-access-governance",
        purpose="Grant least-privilege SonarQube access based on repository membership.",
        inputs=[
            "identity",
            "repository_member",
            "requested_role",
            "owner_approval",
            "security_approval",
        ],
        standard_tools=[
            "identity.lookup",
            "repository.membership_check",
            "sonarqube.grant_access",
            "audit.record",
        ],
        workflow=[
            ToolStep(id="identity", tool="identity.lookup", instruction="Verify requester."),
            ToolStep(
                id="membership",
                tool="repository.membership_check",
                instruction="Verify project membership.",
            ),
            ToolStep(
                id="grant",
                tool="sonarqube.grant_access",
                instruction="Grant project-scoped access.",
            ),
            ToolStep(id="audit", tool="audit.record", instruction="Record access evidence."),
        ],
        escalation_tool="security.request_approval",
        issue_templates=[
            "Developer requests access to project quality dashboard",
            "New team member needs SonarQube project access",
            "QA engineer needs issue triage permissions",
            "Repository maintainer needs scan visibility",
            "Developer moved to a new project",
            "Read-only quality access expired",
        ],
        resolution_templates=[
            (
                "Verified identity and repository membership, granted project-scoped user access, "
                "validated scope, and audited the change."
            ),
            (
                "Confirmed project ownership, added standard SonarQube access without admin "
                "rights, and recorded evidence."
            ),
        ],
        standard_attributes={
            "employment_status": "active",
            "repository_member": True,
            "requested_role": "user",
            "owner_approval": True,
            "security_approval": False,
        },
        held_out=[
            case(
                "Repository member requests standard project access",
                {
                    "employment_status": "active",
                    "repository_member": True,
                    "requested_role": "user",
                    "owner_approval": True,
                    "security_approval": False,
                },
                "RESOLVE",
            ),
            case(
                "Developer requests SonarQube administrator role",
                {
                    "employment_status": "active",
                    "repository_member": True,
                    "requested_role": "admin",
                    "owner_approval": True,
                    "security_approval": False,
                },
                "ESCALATE",
                ["admin", "security approval"],
            ),
            case(
                "Contractor without repository membership requests access",
                {
                    "employment_status": "active",
                    "repository_member": False,
                    "requested_role": "user",
                    "owner_approval": False,
                    "security_approval": False,
                },
                "DENY",
                ["repository membership", "deny"],
            ),
        ],
        new_cases=[
            case(
                "New developer joins an existing repository team",
                {
                    "employment_status": "active",
                    "repository_member": True,
                    "requested_role": "user",
                    "owner_approval": True,
                    "security_approval": False,
                },
                "RESOLVE",
            ),
            case(
                "Maintainer requests global SonarQube admin",
                {
                    "employment_status": "active",
                    "repository_member": True,
                    "requested_role": "admin",
                    "owner_approval": True,
                    "security_approval": False,
                },
                "ESCALATE",
                ["admin", "security approval"],
            ),
            case(
                "External user without repository membership requests access",
                {
                    "employment_status": "active",
                    "repository_member": False,
                    "requested_role": "user",
                    "owner_approval": False,
                    "security_approval": False,
                },
                "DENY",
                ["repository membership", "deny"],
            ),
        ],
    ),
}


def definition(category: str) -> CategoryDefinition:
    try:
        return CATEGORIES[category]
    except KeyError as error:
        raise ValueError(f"unknown category: {category}") from error


def materialize_cases(category: str, split: str, cases: list[dict[str, object]]) -> list[Ticket]:
    return [
        Ticket(
            id=f"{category.upper()}-{split[:1].upper()}{index:04d}",
            category=category,
            split=split,  # type: ignore[arg-type]
            issue=str(item["issue"]),
            attributes=item["attributes"],  # type: ignore[arg-type]
            required_policy_terms=item["required_policy_terms"],  # type: ignore[arg-type]
            expected_outcome=item["expected_outcome"],  # type: ignore[arg-type]
        )
        for index, item in enumerate(cases, start=1)
    ]
