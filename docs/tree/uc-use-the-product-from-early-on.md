---
id: uc-use-the-product-from-early-on
type: use-case
title: Use the product from early on
parent: fr-a-usable-product-exists-early
sources:
- 'Owner design discussion of 2026-10-06: what the owner does with Agentos (its use cases)'
mechanism: |-
  Stage 1. Each action of the shell goes to code or to a puntal; the UI shows progress at once; the
  owner's accept, reject or retry is recorded against the invocation. Any use with feedback or
  telemetry is also a test.
implementation: |-
  The recording half (#115): `agent_os/product/puntal/telemetry/feedback.py` and `puntal_task.sh
  feedback` write accept, reject or retry to `.cache/puntal/feedback.jsonl` keyed by `invocation_id`,
  with the versions of the invocation judged; the generic shell API is `puntal_task.sh --json`
  (`agent_os/product/puntal/json_api.py`). The shell itself -- routing each action to code or to a
  puntal and the progress UI -- is the host app's code and is not implemented here.
---
The owner uses the product from very early on, while much of it is still improvised. That use
is what decides what gets consolidated first.
