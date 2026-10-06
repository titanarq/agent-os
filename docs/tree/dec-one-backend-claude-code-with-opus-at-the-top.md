---
id: dec-one-backend-claude-code-with-opus-at-the-top
type: decision
title: One backend, Claude Code; Opus only at the top, in minimal use
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, point 4 of the global goals
premises:
- The owner works with Claude Code on Sonnet 5.5, or the Anthropic model that replaces it
- One model and one CLI remove the cross-backend machinery from the daily path
rejected_alternatives:
- option: Workers on Qwen and Claude only for reviews (docs/adr/2026-09-16-workers-run-on-qwen-and-claude-only-reviews.md)
  reason: The owner left Qwen aside for v2
  basis: stated
- option: The refiner and task writing on Opus (docs/adr/2026-09-29-claude-roles-default-to-sonnet-5-5-and-agent-models-are-config.md)
  reason: 'The owner: Opus only for the highest level, in minimal use'
  basis: stated
review_triggers:
- The Claude Code window cannot carry the work
- A successor model changes the cost picture
---
Every role runs on Claude Code. Sonnet for every role except the custodian and the consolidator,
which run on Opus and rarely. The substrate's multi-backend machinery stays, configured with one
backend; a host's own config/agents.yaml is changed by that host.
