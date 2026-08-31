# R2-EXTRACTION — Grounded context to Thought Graph

Issue: #40

## Objective
Implement `context -> ThoughtGraph` with exact grounding, uncertainty and a manual non-LLM bypass.

## Prerequisites
R0-SYNTHESIS ACCEPTED, R1-SCHEMA ACCEPTED, R1-INTERFACES ACCEPTED. Use R1-BENCHMARK when accepted.

## Ownership
`src/extraction/` and extraction tests/fixtures. Use public graph/interfaces only.

## Required outputs
- source registration/hash and exact span anchors
- closed-schema nodes/edges with confidence and abstention
- polarity/modality/direction handling
- Knowledge DNA linking hooks without live-network hot-path dependence
- canonical post-processing
- manual graph bypass through the same validator/model
- repeat-extraction evaluation

## Acceptance
Use issue #40 and accepted synthesis thresholds. No ungrounded object may be silently accepted. Manual input must reach the same downstream interfaces without an LLM.