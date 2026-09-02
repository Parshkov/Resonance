# Resonance Privacy and Data Use — Pilot Contract

This document defines the intended privacy contract for the hosted Resonance pilot. It is deliberately conservative and must be kept aligned with the implementation. If the product cannot enforce a statement below, the release must either implement the control or revise the statement before accepting real users.

## What Resonance is designed to store

For a normal shared session, Resonance should persist only the minimum data needed to provide the product:

- a pseudonymous user/profile identifier;
- owned session records;
- validated, versioned Thought DNA and provenance;
- explicit consent/share choices;
- optional consented display profile;
- optional consented **coarse** location;
- timestamps and revocation/deletion state;
- audit/security events with minimized payloads;
- collaboration content (intro state, messages, workspace notes/tasks/artifact metadata) only for participating users.

### Raw conversation text

Raw chat/conversation text is **not required for structural discovery** and should not be retained by default when it is used only to prepare Thought DNA. A selected excerpt may be processed transiently to create a prepared Thought DNA preview. Persisting raw source text requires a separate explicit product purpose and user-visible choice.

## Preparation is not sharing

The intended state machine is:

`draft -> prepared_preview -> shared | discarded`

Preparing or previewing a Thought DNA artifact does not make it discoverable. The user must explicitly approve sharing before the artifact enters the discoverable corpus/index.

## What other people may receive

A discovery result may contain only consented fields needed to understand a match, for example:

- pseudonymous identity/session reference;
- structural classification/score and evidence;
- selected display/topic labels if shared;
- coarse location if separately shared;
- collaboration availability/status.

Unshared Thought DNA, raw private conversation text, exact location, account credentials, private workspace content, and private contact information must not be returned through discovery.

## Location

Location is optional and presentation-only.

- Exact GPS/address is not required for the pilot.
- Resonance should store/share only coarse location explicitly approved by the user.
- Location must never change structural matching rank or score.
- Missing location must not reduce resonance quality.
- Aggregate/heatmap views must apply anti-inference rules such as suppressing small buckets and must exclude hidden/revoked users.

## Introductions and communication

Discovery does not disclose private contact details.

The intended flow is:

`available -> requested -> accepted | declined | cancelled`

Only after mutual acceptance may the participants enter a private Resonance collaboration channel/workspace. Even then, the pilot does not require disclosure of email, phone number, or legal identity; communication may remain inside Resonance.

## Shared workspaces

Workspace content is visible only to active authorized members. A workspace may include multiple people and their authorized agents.

Workspace notes, tasks, messages, artifacts, and linked source sessions are **not automatically republished into discovery**. A member must explicitly create/share a separate discovery session under normal consent rules if they want workspace-derived Thought DNA to become discoverable.

Leaving or removal must revoke access to future workspace-private state and private media delivery.

## User controls required before public pilot

The hosted pilot must provide server-enforced controls to:

- revoke discovery sharing;
- delete a session;
- change display/location/collaboration consent;
- leave a workspace;
- block another user;
- request an export of owned pilot data;
- request account deletion/anonymization.

Revocation must remove live discoverability immediately. Backup deletion may be asynchronous if the retention window is documented.

## Agents and untrusted content

A user's agent may act only with that user's authorization and access only data the user is permitted to access.

Text, labels, messages, notes, and artifacts originating from other users are untrusted user-generated content. They must not be interpreted as system instructions by Resonance or by an integrating agent. Tool schemas/descriptions remain static trusted application code.

## Logs and analytics

Operational logs should contain request/correlation IDs, status, latency, and minimized audit/security metadata. They should not contain raw Thought DNA, private messages, access tokens, contact details, or full authorization headers by default.

The canonical competition/pilot path should not require third-party advertising or behavioral analytics.

## Retention

The exact pilot retention periods must be documented in the deployed release. Until those periods are finalized, do not claim immediate erasure from encrypted backups after user deletion. Live access/discoverability must still be revoked immediately.

## Security and privacy contact

Until a dedicated private reporting address is published, contact the repository owner through GitHub and request a private channel. Do not post credentials, exploit details, or real user data in public issues.

## Release condition

This document describes a target contract, not evidence that every control is already deployed. Real volunteer onboarding must remain closed until #89 and the deployment/security review confirm the hosted release enforces the applicable controls.
