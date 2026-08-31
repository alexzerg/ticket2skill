# Runbook Drift architecture

```mermaid
flowchart LR
    T[200 timestamped Jenkins tickets] --> M[Timeline Miner\nGemini 3.5]
    C[Authoritative migration log] --> M
    M --> E[Four architecture eras]
    E --> X[Exact legacy allowlist\nParis · Barcelona · NYC]
    E --> S[Temporal Skill Compiler\nGemini 3.5]
    X --> S
    S --> R[Deterministic temporal replay]
    R --> I[Current-Era Incident Resolver]
    I --> P[JCasC GitOps patch]
    R --> F[(Firestore temporal registry)]
    P --> F
    F --> Z[Downloadable current skill ZIP]
```

## Authority order

1. Current architecture declaration
2. Migration change log
3. Recent current-era tickets
4. Older historical tickets
5. Historical frequency

A high-frequency old action cannot override an explicit migration event. A migration event may retain a bounded exception, but only as an exact allowlist. The current demo retains `jenkins-paris`, `jenkins-barcelona`, and `jenkins-NYC`; no wildcard VM route exists.

## Agents

- **Timeline Miner:** detects operational eras from timestamps, tools, resolutions, and architecture evidence.
- **Temporal Skill Compiler:** creates the current workflow, converts retired actions into negative constraints, and preserves exact legacy exceptions.
- **Current-Era Incident Resolver:** routes an exact allowlisted controller to its scoped VM runbook; every other incident uses current tools and produces a JCasC patch.

## Deterministic publication gate

Publication requires all temporal checks to pass: current era, the exact three-controller legacy allowlist, bounded exact-match routing, GKE agent diagnostics, Workload Identity, Git pull request, JCasC validation, Argo CD diff-before-sync, stale VM rejection for non-allowlisted targets, direct Helm rejection, and valid patch fields.
