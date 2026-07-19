# Verification record

## Automated checks

Run from the repository root:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/run_gold_eval.py
python scripts/run_governance_corpus.py
python scripts/privacy_audit.py
node --check web/app.js
```

The automated suite covers:

- event ordering, idempotency, reset preservation, path bounds, and hash-chain tamper detection;
- evidence projection and exclusion of AI prompts;
- question source anchors, deduplication, leading/generic-question rejection, and explicit unknowns;
- same-case multi-round behavior, custom synthetic rounds, stale analyses, and save-without-regeneration semantics;
- live Codex command isolation, model selection, schema normalization, and source-ID validation;
- local HTTP routes, input bounds, export declarations, and security headers;
- repository privacy patterns.

Latest local candidate verification on 2026-07-20:

- 47 / 47 automated contract tests passed;
- four-round synthetic gold replay completed with 7 analyses, 3 practitioner answers, and 1 formal snapshot;
- three-case synthetic governance corpus completed with 8 rounds, 15 analyses, 7 practitioner answers, and 3 formal snapshots;
- report-versus-observation separation and later-evidence inference revision both passed as focused conformance cases;
- event-ledger hash chain verified end to end;
- privacy audit completed with 0 findings;
- JavaScript syntax verification passed.

## Browser checks

The verified judge path covered:

1. loading a fresh synthetic case;
2. running the first replay;
3. confirming the required question is excluded from evidence;
4. adding the suggested practitioner answer as evidence;
5. confirming the analysis becomes stale;
6. rerunning and reaching the save-ready state;
7. adding the second source round to the same case;
8. rerunning and receiving the mechanism question;
9. checking desktop and 390 × 844 responsive layouts;
10. opening the 90-second Judge Tour and confirming progress changed from 0 / 5 to 1 / 5 after the first real Replay event;
11. checking browser warnings and errors.

## Live Codex smoke check

The tested environment reported an existing ChatGPT sign-in. A synthetic-only live request completed with the `gpt-5.6-luna` model and returned an English, schema-conforming, source-cited response. The generic `gpt-5.6` slug was separately rejected by that ChatGPT-account route, so the application does not claim that slug succeeded in the tested environment.

Live behavior may vary by judge account entitlement and installed Codex version. Replay mode is the guaranteed no-entitlement path.

## Known limits

- This is a local Build Week prototype, not a hosted multi-user system.
- The public repository demonstrates the core reflection loop, not every private ObserveOS module.
- Replay mode is deliberately scripted and does not infer beyond predefined or verbatim custom synthetic sources.
- The browser Judge Tour exposes the full longitudinal case; the two focused conformance cases run through the command-line corpus evaluator.
- Citation validation confirms referenced evidence event IDs exist; semantic support remains human-reviewed.
- A reflection question requires a non-empty case anchor and valid evidence IDs, but anchor-to-source semantic fit is not automatically validated.
- Browser-added custom text is user-declared synthetic and is not automatically de-identified or content-verified.
- The saved snapshot is not yet bound to a reviewer identity or UI-render digest.
- The privacy audit is pattern-based and must be paired with human release review.
- MIT licensing is selected. The public GitHub repository, Public YouTube demo, and submitted Devpost page have been read back.
