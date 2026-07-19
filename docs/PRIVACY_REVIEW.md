# Privacy review

## Included

- One fictional case (`DEMO-CASE-001`).
- Four fictional source packets.
- Fictional suggested practitioner answers.
- Local synthetic event history.
- Public-safe architecture and submission documentation.

## Excluded

- Real case records or identifiers.
- Real recordings, transcripts, images, or attachments.
- Client, practitioner, staff, or vendor contact details.
- Mailbox or calendar content.
- Operations databases, payment data, advertising data, or live-platform exports.
- API keys, tokens, cookies, browser profiles, or Codex authentication files.
- Private repository paths, configuration, or production credentials.

## Runtime boundaries

- The server refuses non-loopback bind addresses.
- Replay mode is deterministic and makes no model call.
- Live mode passes only the browser’s fictional evidence projection to an ephemeral, read-only Codex process.
- The child process receives a restricted environment-variable allowlist.
- Runtime history is ignored by Git.
- The export manifest declares `synthetic_only: true` and reports hash-chain verification.

The shipped fixture is verified fictional. Browser-added custom text must also be synthetic, but that status is user-declared; the application does not automatically de-identify or content-verify custom input.

## Release check

Run:

```bash
python scripts/privacy_audit.py
```

The audit searches text files for common private Windows paths, secret formats, filled API-key assignments, secret-bearing environment files, and generalized private-mailbox shapes. It is a useful release gate, not a substitute for human review.

Before publication, a human must still inspect the repository diff, demo recording, Git metadata, and upload form.
