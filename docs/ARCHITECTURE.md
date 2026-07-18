# Architecture

## Runnable slice

The public app is a local, standard-library Python server with a static HTML/CSS/JavaScript interface.

```text
Browser UI
  -> local JSON API
      -> ObserveOSService
          -> append-only EventStore
          -> evidence projection
          -> deterministic replay OR isolated Codex CLI
          -> reflection normalization
          -> formal-save gate
```

There is no external database, web framework, package manager, or API-key integration.

## Core components

| Component | Responsibility |
|---|---|
| `app.py` | Loopback-only HTTP server, bounded JSON routes, security headers, static assets |
| `observeos/event_store.py` | Append-only JSONL events, event sequence, idempotency keys, hash-chain verification |
| `observeos/reflection.py` | Evidence projection, excluded AI prompts, stable question IDs, question hard gates |
| `observeos/replay_engine.py` | Deterministic judge replay using the fictional case |
| `observeos/codex_runner.py` | ChatGPT-authenticated Codex execution, evidence-only prompt, JSON schema and citation validation |
| `observeos/service.py` | Same-case multi-round state, stale-result detection, save gate, export projection |
| `web/` | Responsive judge interface and workflow controls |

## Event model

Each event contains a stable ID, monotonically increasing sequence, round, timestamp, previous hash, and current hash.

1. `case_created`
2. `source_added`
3. `analysis_generated`
4. `reflection_question_asked`
5. `reflection_answered`
6. `formal_snapshot_saved`

Events are never overwritten. A new source or practitioner answer makes an older analysis stale, but the older analysis remains visible in history.

## Live-model isolation

Live review launches `codex exec` in a temporary directory and uses:

- the existing Codex ChatGPT authentication context;
- an ephemeral session;
- read-only sandboxing;
- ignored user configuration and repository rules;
- a strict JSON output schema;
- a sanitized child-process environment;
- a prompt containing only the fictional evidence projection.

The returned source IDs are validated against the actual evidence event IDs. Unknown citations fail the request instead of being displayed as grounded output.

## Whole-practice boundary

The product vision is broader than the public slice. Intake, transcription, case truth, knowledge, operations, public sites, and content production may coordinate, but each keeps its own truth source. The Reflection Loop is the reusable control plane for admitting information into a reviewed case output; it is not a universal database.
