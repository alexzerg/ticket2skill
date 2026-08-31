# Plan

1. Add a pure v4-to-v5 lifecycle transition.
2. Replay both DriftUpdate and complete TemporalSkill v5.
3. Publish v5 under a new registry ID and mark v4 publication stale.
4. Switch state, router, workflow, patch, Firestore evidence, and downloads to v5.
5. Add inputs, guardrails, normalized placeholders, tests, deployment, and live evidence.
