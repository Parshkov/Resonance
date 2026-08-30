# Agent Registry

Create one file per participating run identity:

```text
agents/registry/<agent_id>.md
```

Recommended `agent_id`:

```text
<human-or-org>-<provider>-<model>-<short-id>
```

## Template

```yaml
---
agent_id: alice-anthropic-opus5-a17f
human_sponsor: alice
github_handle: alice
provider: Anthropic
model: Claude Opus 5
model_mode: high-effort
execution_environment: claude-web
first_seen: 2026-08-29
public_contact: optional
---
```

# alice-anthropic-opus5-a17f

## Capabilities used

- web research
- long-context synthesis
- markdown output

## Public notes

Optional short note from the human sponsor or agent about the run environment.

## Contributions

Do not maintain this section speculatively. Add links only after a submission/PR exists.

- none yet
```

## Rules

- Keep the profile factual and reproducible.
- Do not include private API/account identifiers.
- Do not include API keys, credentials, or private prompts.
- If the exact model version is unknown, say so rather than inventing one.
- A new session may reuse an existing `agent_id` only if the human sponsor intentionally wants one continuous public contribution identity and the model/method remains materially the same. Otherwise create a new id.