# Ticket2Skill architecture

## Agent roles

### Pattern Miner

Reads resolved ticket evidence and identifies repeated human workflows. It may only infer policies visible in the training evidence.

### Skill Builder

Produces a strict `SkillSpec`: inputs, allowed tools, ordered workflow, policy rules, and success criteria. Structured output is enforced with Pydantic and Gemini response schemas.

### Replay Critic

Receives only the generated skill and held-out failure evidence. It produces a complete next version rather than mutating production state.

### Registry Publisher

Accepts only a 100% replay result, writes a versioned Firestore record, and creates a portable artifact package.

## Trust boundaries

- Gemini never writes directly to Firestore or executes enterprise tools.
- Generated tool names are restricted by a typed allowlist.
- Held-out cases are never included in initial skill generation.
- Replay decisions and tool trajectories are deterministic.
- Publication requires a 100% replay score.
- All tickets are synthetic hackathon fixtures.

## Cloud resources

| Resource | Purpose |
|---|---|
| Cloud Run `ticket2skill` | Public API and UI |
| Vertex AI global endpoint | Gemini 3.5 structured generation |
| Firestore `(default)` | Versioned agent skill registry |
| Artifact Registry `ticket2skill` | Container images |
| Cloud Build | Reproducible image builds |
