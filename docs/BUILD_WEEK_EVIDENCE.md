# Build Week evidence

## Submission identity

- Project: **ObserveOS — The Self-Improving Clinic Operating System**
- Track: **Work & Productivity**
- Runnable core: **CaseAgent Reflection Loop**
- Primary Codex development session ID: `019f6743-1883-7b93-9f61-4a34a96d6e1f`
- Local Build Week baseline commit: `770d097610484d4fac34b288b41d5e8d718242d3`
- Build date for this public-safe edition: `2026-07-18` (Asia/Taipei)

## Prior workflow versus Build Week implementation

ObserveOS existed before Build Week as a private, evolving whole-practice workflow. During Build Week, Codex and GPT-5.6 were used to extract its evidence-governance core and build a new, independently runnable, synthetic-only public implementation: the local app, event model, evidence projection, deterministic Replay and optional Codex paths, schema gates, synthetic gold evaluation, contract tests, and release checks.

The public CaseAgent Reflection Loop is the runnable submission. The broader private modules and clinical decision logic base provide product lineage; they are not hidden dependencies required by a judge.

## What Codex and GPT-5.6 did

Codex and GPT-5.6 were used to:

1. inspect the prior system lineage and extract a privacy-safe submission thesis;
2. convert expert truth-boundary decisions into an executable evidence contract;
3. design the append-only multi-round event model;
4. implement the local service, browser interface, deterministic replay, and live Codex route;
5. build JSON-schema, source-ID validation, and bounded-question gates around model output;
6. turn failure modes into tests, a gold evaluation, and a privacy audit;
7. verify the real browser workflow and ChatGPT-authenticated Codex path.

## Development model versus runtime model

The Build Week development process used GPT-5.6 in Codex to perform the architectural work above. The local live demo uses the GPT-5.6 model slug available to the signed-in Codex account. In the verified environment that was `gpt-5.6-luna` at medium reasoning effort. The deterministic replay provides the same evidence-contract demonstration when a judge does not have a compatible live entitlement.

No OpenAI API key was created or used for the application.

## Reproducible proof in the repository

The strongest proof is not a screenshot of a model name. It is the repository’s inspectable behavior:

- `schemas/codex_analysis.schema.json` constrains live output.
- `observeos/codex_runner.py` passes only evidence, validates referenced evidence IDs, and launches an isolated Codex session.
- `tests/test_codex_runner.py` verifies the model command and failure boundaries.
- `evals/gold/synthetic_multiturn_gold.json` defines expected multi-round behavior.
- `scripts/run_gold_eval.py` replays that behavior from a clean temporary store.
- `scripts/privacy_audit.py` checks the public tree for common secret and private-path patterns.

## Submission asset status

- public Git repository: released and read back from `https://github.com/paul800901/ObserveOS-Build-Week`;
- repository license: MIT;
- YouTube demonstration: uploaded, playback-verified, and confirmed Public at `https://youtu.be/VP0IDC0gg4g`;
- Devpost submission: submitted and publicly readable at `https://devpost.com/software/observeos-the-self-improving-clinic-operating-system`.

The original local baseline remains private because its author metadata contains a personal email address. The public repository is released from the same verified tree as a clean, privacy-safe commit using the GitHub noreply identity.
