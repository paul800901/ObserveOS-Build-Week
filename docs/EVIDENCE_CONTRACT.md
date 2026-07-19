# Evidence contract

The CaseAgent Reflection Loop treats epistemic boundaries as executable behavior, not prompt advice.

## Invariants

1. Every supported finding cites at least one valid evidence event.
2. Every inference cites evidence, shows a reason, and declares uncertainty.
3. “Not observed,” “not tested,” and “I do not know” are valid results.
4. An AI-generated question is never evidence.
5. A practitioner answer is new evidence with explicit provenance.
6. New evidence makes the prior analysis stale.
7. An unresolved required question blocks a formal snapshot.
8. Saving stores the current normalized analysis; it does not trigger another model call.
9. Historical events are append-only and hash-chain verifiable.
10. A repeated analysis request with unchanged evidence reuses the existing result.

## Reflection hard gates

A model-generated reflection question is kept only when it:

- provides a non-empty case anchor;
- cites valid evidence event IDs;
- could materially improve the main reasoning path, observation boundary, intervention effect, retest, follow-up, safety, or alternative explanation;
- is not generic, leading, or already answered;
- fits the visible question budget.

Questions that fail these checks are removed and surfaced as safety flags in the analysis payload.

Citation validation confirms that the referenced evidence IDs exist. The prototype does not yet compare the anchor text semantically with the cited source; semantic fit remains human-reviewed.

## Why questions are excluded

An AI question can influence memory. Treating the question itself as case evidence would allow the model to seed its own future conclusion. The ledger therefore keeps questions in interaction history while the evidence projection excludes their text. Only the human’s answer, including an explicit unknown, can enter the next evidence set.

## Save behavior

The snapshot gate checks:

- an analysis exists;
- no newer evidence exists after that analysis;
- every required reflection question is answered.

When ready, the snapshot stores the current normalized analysis payload and its evidence digest without calling the model again. The prototype does not yet bind that snapshot to a reviewer identity or UI-render digest.
