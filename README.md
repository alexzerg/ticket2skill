# Runbook Drift

**Historical tickets know how the system used to work—not how it works now.**

Runbook Drift is a temporal operations agent built for the All Things Agentic Hackathon. Gemini 3.5 analyzes 200 historical Jenkins incidents together with an authoritative migration log, discovers four architecture eras, retires stale procedures, and publishes a recovery skill for the current operating model.

**Live demo:** https://ticket2skill-1027721936124.us-central1.run.app

## The problem

A support or operations agent trained on historical tickets may confidently recommend the most common old answer.

For this company, 80 of 200 Jenkins tickets were resolved when Jenkins ran on 40 Google Compute Engine VMs:

```text
SSH to the affected VM → inspect journalctl → systemctl restart jenkins
```

That answer is now dangerous. The company subsequently migrated through four eras:

| Era | Tickets | Architecture | Valid recovery model |
|---|---:|---|---|
| VM | 80 | 40 independent Compute Engine VMs | SSH, systemctl, local configuration |
| Helm | 55 | Jenkins consolidated on GKE | Helm values and Kubernetes rollout |
| GitOps | 40 | JCasC stored in Git and reconciled by Argo CD | Pull request, JCasC validation, Argo diff/sync |
| Current | 25 | Ephemeral GKE agents with Workload Identity | JCasC pod template and identity binding through GitOps |

Historical frequency says “restart the VM.” Temporal context says those VMs no longer exist.

## Synthetic Jira connector

The demo starts with a realistic but explicitly synthetic Jira integration:

```text
Endpoint: acme-ops.atlassian.net/rest/api/3/search
Auth: OAuth 2.0
Project: OPS
Selected label: jenkins
JQL: project = OPS AND labels = "jenkins" AND status = Done ORDER BY resolved ASC
Imported issues: OPS-1001 … OPS-1200
```

The user first checks the connector and imports 200 resolved issues, then asks Gemini to discover the temporal architecture eras. No real Jira tenant, credentials, or corporate data are used.

## Demo incident

```text
Thirty-seven Jenkins builds are queued.
Ephemeral GKE agents fail to start after a service-account change.
The controller is healthy, but new agent pods cannot authenticate.
```

Runbook Drift contrasts two answers:

```text
HISTORICAL MAJORITY — STALE
SSH to the affected Compute Engine VM and restart Jenkins with systemctl.

CURRENT TEMPORAL SKILL — VALID NOW
Inspect ephemeral agent pods and Workload Identity, update the JCasC pod template through a Git
pull request, validate the configuration, inspect Argo CD diff, and sync after approval.
```

## Agent pipeline

1. Timeline Miner reads all 200 tickets, timestamps, tools, resolutions, and architecture labels.
2. Gemini 3.5 reconciles ticket history with the authoritative migration change log.
3. Temporal Skill Compiler creates `jenkins-current-recovery:v4`.
4. Deterministic temporal replay checks that retired actions cannot re-enter the workflow.
5. Current-Era Incident Resolver generates a valid JCasC patch for the new incident.
6. Registry Publisher writes the timeline, skill, patch, and replay evidence to Firestore.
7. A downloadable ZIP becomes the current Jenkins recovery artifact.

## Tangible result

```text
jenkins-current-recovery-v4/
├── skill.yaml
├── timeline.json
├── deprecated-actions.json
├── jcasc-patch.yaml
├── eval-report.json
└── README.md
```

The skill explicitly retires:

- SSH and systemctl recovery on the removed Compute Engine fleet;
- local Jenkins controller configuration edits;
- direct Helm upgrades after GitOps adoption;
- persistent direct kubectl mutations.

The generated patch targets the current JCasC Kubernetes agent template and Workload Identity service account.

## Continuous drift monitoring

Initial backfill is only the onboarding step. After publication, Runbook Drift monitors new architecture evidence from Git, Argo CD, Google Cloud, and resolved incidents through Pub/Sub.

The live demo sends a real `architecture.drift` message to the `runbook-drift-events` topic. A new identity migration retires the `iam.gke.io/gcp-service-account` annotation and adopts direct Workload Identity Federation principal binding with the `ci-build-agent` Kubernetes service account.

```text
Pub/Sub architecture event
→ v4 marked STALE
→ Gemini Drift Agent generates v5
→ deterministic drift replay reaches 100%
→ v5 published to Firestore as CURRENT
```

This turns a one-time history import into a continuous skill lifecycle.

## Why it is different

Historical-ticket training, agent evaluation, and workflow induction already exist. Runbook Drift addresses the failure mode they create when enterprise architecture changes over time.

> **Old tickets describe what worked then. Runbook Drift determines what is valid now.**

The migration log has higher authority than historical frequency. Old tickets remain useful as temporal evidence, but retired tools and architectures become negative constraints rather than recommendations.

## Google Cloud architecture

- Gemini 3.5 Flash through Vertex AI global endpoint
- Google GenAI SDK for Timeline Miner, Temporal Skill Compiler, and Incident Resolver
- Cloud Run for the public application
- Pub/Sub for continuous architecture-drift events
- Firestore for versioned temporal skill evidence
- Cloud Build and Artifact Registry for delivery
- Google Compute Engine and GKE as the historical architecture storyline

Google Cloud project: `ticket2skill-agentic-26`. All tickets and infrastructure evidence are synthetic. No corporate data or systems are used.

## Run locally

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
make run
```

Deploy:

```bash
make deploy
```
