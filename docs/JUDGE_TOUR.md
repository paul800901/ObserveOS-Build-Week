# Judge tour

## Fastest visible route

1. Start the local app and choose **90-second judge tour**.
2. Leave **Replay** selected and run the first evidence review.
3. Confirm that the client report remains a report and that one anchored question appears outside the evidence list.
4. Use the demo answer and add it as practitioner evidence.
5. Confirm that the old analysis becomes stale, while the AI question remains excluded from evidence.
6. Rerun Replay, add the remaining source rounds, and answer only what is actually known.
7. When all five tour checks are verified, save the current normalized analysis without regeneration.

The progress card is derived from the append-only event ledger. It does not mark a step complete merely because a button was clicked.

## Three-case corpus route

Run:

```bash
python scripts/run_governance_corpus.py
```

Expected result:

- 3 fully fictional cases;
- 8 source rounds;
- 15 deterministic analyses;
- 7 practitioner answers that become evidence;
- 3 current-analysis snapshots saved without a second analysis call;
- 3 verified hash chains.

The cases test:

1. **Longitudinal evidence:** report, observation, intervention/retest, and follow-up remain traceable across four rounds.
2. **Source-role conflict:** perceived effort and observed hand contacts remain separate instead of being silently merged into a contradiction.
3. **Inference revision:** later non-replication makes the earlier analysis stale and weakens the earlier bounded inference.

The two focused cases are public, invented conformance cases. They encode governance patterns only; they are not de-identified exports of private cases.
