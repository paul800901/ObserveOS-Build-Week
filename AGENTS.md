# Public submission rules

This repository is the privacy-safe Build Week edition of ObserveOS.

1. Use fictional data only. Never add real cases, recordings, contacts, emails, operational records, credentials, or private filesystem paths.
2. Preserve the evidence boundary: an AI question is interaction history, not evidence; only a practitioner answer may become evidence.
3. Preserve append-only history, evidence citations, explicit unknowns, stale-analysis detection, and save-current-analysis-without-regeneration behavior.
4. Keep the demo local by default. Do not broaden the bind address beyond loopback.
5. Do not add an OpenAI API-key requirement. Live mode must continue to use an existing Codex sign-in.
6. Keep replay mode deterministic and usable without network or model access.
7. Run the unit tests, gold evaluation, JavaScript syntax check, and privacy audit before release.
8. Do not publish or change the license without the creator’s explicit review.
