# R12 identity / authentication / consent

`src.identity` is the privacy boundary between an authenticated Resonance subject and the durable R11 corpus/persistence layer.

## Contract

- Pseudonymous accounts are sufficient; no email or legal identity is required.
- Opaque browser access, CSRF, and account-recovery secrets are returned only to the client. Persistence receives SHA-256 digests, never plaintext credentials.
- Browser sessions are durable and revocable because issuance/revocation is event-sourced into R11 audit storage through `R11IdentityBackend`.
- A caller never supplies the acting `user_id` to a protected mutation. `IdentityService` resolves it from the credential and checks the durable thought-session owner server-side.
- Thought sessions are private on creation. Sharing is a separate confirmed `set_consent` operation.
- Discovery, display profile, coarse location, and intro availability are independent user choices. The first three project exactly into the accepted R11/R7 consent record; intro availability remains a non-ranking identity-policy flag.
- Revoke/delete fail closed: corpus consent is cleared first by R11 and identity overlay consent is recorded false.
- Human UI and browser WebMCP use the same cookie-session adapter policy, including CSRF checks. A later bearer remote-MCP/API path calls the same service authorization policy.
- Location is presentation-only. Identity rejects obvious exact-address/exact-GPS fields and permits only city-level precision; schema validation remains R11's responsibility.
- Other-user content is treated as untrusted UGC by agent-facing adapters (`untrusted_content_hint = True`).

## R11 integration

`R11IdentityBackend` wraps the declared R11 `LiveCorpusService` plus its `PersistenceRepository`. R12 does not implement a database, migration, index, matcher, or alternative persistence path. The adapter's `src.persistence.models.AuditEvent` import is lazy so this branch remains testable while canonical R11 is still pending review.

The identity event payload intentionally excludes raw Thought DNA, contact details, plaintext tokens, plaintext CSRF values, and plaintext recovery credentials.

## Validation

Self-contained acceptance-oriented tests:

```bash
python3 -m unittest tests.test_identity_consent -v
python3 -m compileall -q src tests
```

The R12 branch is based on `main` while R11 remains a separate submitted canonical lane, so the self-contained suite uses a deterministic fake of the declared R11 seam. Exact integration must be re-run against the accepted R11 head before R12 maintainer acceptance.
