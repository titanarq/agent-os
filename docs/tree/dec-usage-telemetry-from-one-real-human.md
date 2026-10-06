---
id: dec-usage-telemetry-from-one-real-human
type: decision
title: Usage telemetry comes from one real human using the shell
state: in-force
decided: 2026-10-04
sources:
  - "docs/AGENTOS_V2_PLAN.md, 'Founding decisions' row 3 and 'Phase 4'; approved by the owner in the design discussion of 2026-10-04"
premises:
  - "Simulated usage measures the simulator's bias, not demand"
rejected_alternatives:
  - option: "Simulated usage: synthetic users or agents driving the shell to produce the telemetry"
    reason: "The premise argues it: simulated usage measures the simulator's bias, not demand"
    basis: stated
review_triggers:
  - "A second real user exists"
---
The telemetry that decides which use cases get hardened into real code (frequency, suffered
latency, gap notes, errors) comes from one real human using the live shell, not from simulated
usage.
