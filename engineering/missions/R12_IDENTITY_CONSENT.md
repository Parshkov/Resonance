# R12-IDENTITY-CONSENT

## Mission

Implement the smallest real privacy-first pseudonymous account, browser-session, ownership, and consent layer needed by live Resonance users and agents, without changing accepted structural matching semantics or duplicating R11 persistence.

Canonical issue: #84  
Prerequisite checked at claim time: R8-DISCOVERY accepted on #73  
Claim run: `R12-IDENTITY-CONSENT`  
Agent: `parshkov-openai-gpt56sol-r12i-e4c7` / OpenAI GPT-5.6 Sol

## Architecture

`IdentityService` is transport-neutral and authoritative for subject resolution, object ownership, consent mutation, revoke/delete, login/session rotation, logout, and account revoke.

Production persistence is supplied by `R11IdentityBackend`, which wraps the R11 `LiveCorpusService` / `PersistenceRepository` seam. It uses R11 user/thought-session methods directly and stores only minimized identity lifecycle events in R11's durable audit log. There is no identity database, migration, retrieval index, or scoring implementation in R12.

R11 canonical PR #95 was inspected during implementation. The declared handoff surface was `LiveCorpusService`, with durable `PersistenceRepository` methods including user/session operations and `append_audit` / `list_audit`. At implementation time its observed head was `2025e5101f13bee9b1266749059385b3b5a3d1b4`; R11 was still `SUBMITTED / PENDING_REVIEW`, so R12 keeps the adapter structurally typed/lazy and does not treat that exact head as accepted.

## Privacy/security invariants implemented

- private-by-default Thought sessions;
- acting subject derived from opaque credential, never browser/agent `user_id`;
- same not-available error for foreign vs unknown session IDs;
- opaque access/CSRF/recovery secrets with only SHA-256 digests persisted;
- Secure + HttpOnly + SameSite=Strict browser cookie policy metadata;
- CSRF required for cookie-authenticated consent/revoke/delete mutations;
- fresh auth session identifier/token on login and explicit rotation;
- logout/account revoke invalidate durable auth-session state;
- email/legal identity not required: pseudonymous `user_id` + high-entropy recovery credential supports logout/login;
- exact per-session projection of Thought DNA/display/location consent to R11, with intro availability kept separate from structural ranking;
- visible confirmation required for consent/revoke/delete/account revoke;
- revoke/delete clear live discoverability through R11 and clear intro consent overlay;
- identity audit payloads omit raw Thought DNA and plaintext credentials;
- city-level coarse location only; obvious exact-address/GPS fields rejected;
- manual UI and browser WebMCP share the same cookie-session authorization adapter;
- agent-facing adapters mark returned UGC as untrusted.

## Validation evidence

Runtime: Python 3 (container runtime; stdlib only for R12 module/tests).

Commands executed against the exact authored files before GitHub submission:

```text
python3 -m unittest tests.test_identity_consent -v
Ran 11 tests in 0.006s
OK

python3 -m compileall -q src tests
exit 0
```

Covered acceptance scenarios:

1. private creation then exact granular consent projection;
2. cross-user ID substitution rejected with no existence oracle;
3. explicit confirmation + CSRF for cookie mutations;
4. rotation/logout invalidates old credentials;
5. logout -> pseudonymous recovery login preserves owned state without email;
6. process restart restores auth and owned thought state from durable R11-style event/user/session storage;
7. revoke/delete immediately remove the fake live index and clear overlay consent;
8. manual UI and WebMCP produce identical authorization/consent outcomes;
9. identity audit contains no plaintext access, CSRF, recovery secrets, or Thought DNA;
10. account revoke invalidates credentials and removes user's discoverability;
11. already-shared Thought DNA cannot be silently replaced without first revoking sharing.

## Known integration gate

Direct network `git clone` is unavailable in this run environment. The branch therefore does not claim a full repository regression run or a live R11 integration run. Only the exact self-contained commands above were executed. Because R11 is still pending review and not present on this branch's `main` base, maintainer acceptance must re-run R12 against the **accepted** R11 exact head and full regression suite. This limitation is explicit rather than inferred away.

## Handoff

Public surface:

- `src.identity.IdentityService`
- `src.identity.R11IdentityBackend`
- `src.identity.ConsentChoices`
- `src.identity.ManualUIAdapter`
- `src.identity.WebMCPAdapter`
- `src.identity.BearerAgentAdapter`

R12C should prepare a private session/artifact first, then call the confirmed consent/share operation; it must never pass an owner id or consent state through from agent-supplied content. R12B can add rate limiting, request-size controls, CSP/CORS/deployment checks, and independent security review without replacing this authorization service.
