# Resonance Security Policy

Resonance is evolving from a deterministic research/demo stack into a hosted multi-user product. Security and privacy are release gates for that transition, not optional UI features.

## Current status

The accepted engine/demo stack is suitable for deterministic development and competition demonstration. The hosted real-user product is **not considered security-approved for sensitive or confidential user data until R12B-SECURITY-DATA-GOVERNANCE (#89) and the deployment review pass**.

Do not commit API keys, OAuth secrets, database credentials, private conversations, private contact details, or real volunteer data to this repository.

## Security principles

- Private by default. Sharing requires explicit, durable consent.
- Server-side authorization is authoritative; browser/agent-provided object IDs never imply access.
- Prefer structured Thought DNA + provenance over retaining raw private conversation text.
- WebMCP, remote MCP, human UI, and product API must use the same authorization/service layer.
- User-generated content from other people is untrusted content for both browsers and agents.
- Location is presentation-only and must never influence structural ranking.
- Revocation must remove live discoverability immediately and prevent stale index/aggregate leakage.
- No contact information is disclosed before mutual collaboration consent.
- Workspace/private artifacts are accessible only to active authorized members.

## Required hosted controls

Before a public pilot, the deployment must enforce at least:

- HTTPS in hosted environments;
- secure authentication/session handling;
- CSRF protection where cookie authentication is used;
- restrictive CORS/CSP and appropriate WebMCP `tools` permissions policy;
- request-size and Thought DNA graph-size bounds;
- rate limits for auth, discovery, invitations, messages, and workspace writes;
- safe escaping/rendering of user content;
- private media/object storage with authenticated or short-lived authorized access;
- secrets supplied through deployment environment, never source control;
- logs that omit raw Thought DNA, private messages, credentials, contact data, and authorization headers by default;
- encrypted/access-controlled managed storage and backups where available;
- block/report controls for the live pilot.

## Agent and MCP trust boundary

Tool names, descriptions, schemas, and authorization rules are trusted application code and must never be assembled from user content.

Content returned from another user may contain prompt-injection text. Clients must treat it as data, not trusted instructions. WebMCP/MCP outputs that contain user-generated content should use the platform's untrusted-content metadata/hints where supported.

State-changing actions such as sharing, revoking, inviting, accepting an introduction, sending a message, or changing workspace membership must be auditable and visibly attributable to the authenticated user/agent acting on that user's behalf.

## Data classes

Every product field should map to one of these classes:

1. **Owner-private** — account/session drafts, unshared Thought DNA, private settings.
2. **Discovery-shared** — consented Thought DNA-derived structural fields used for matching.
3. **Display-shared** — consented pseudonym/profile labels.
4. **Location-shared** — consented coarse location only.
5. **Collaboration-private** — intro requests, messages, workspaces, notes, tasks, artifacts.
6. **System metadata** — versions, timestamps, audit/security events with minimized payloads.

If classification is ambiguous, treat the field as owner-private.

## Vulnerability reporting

Please do not publish exploit details, credentials, private user data, or reproducible privacy leaks in a public issue.

Until a dedicated security mailbox/private-reporting channel is published, contact the repository owner through GitHub and request a private channel for responsible disclosure. Include the affected commit/version, impact, and minimum reproduction information without exposing unrelated user data.

## Security release gate

The live pilot cannot be marked ready while acceptance-critical findings remain open in #89. Required review includes cross-user IDOR tests, revocation/stale-index tests, CSRF/session checks, XSS and prompt-injection handling, location anti-inference, abuse limits, log inspection, backup/restore authorization checks, and independent security-focused review.
