---
id: fr-nothing-learned-is-lost
type: functional-requirement
title: Nothing learned is lost
parent: goal-improves-with-every-product
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, point 2; extends docs/AGENTOS_V2_PLAN.md
decisions:
- dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check
mechanism: |-
  Stages 1-2. Files in git are the memory of record; a lesson climbs note -> rule -> check, the
  operator's lessons about the mechanism included. Cited telemetry is copied into evidence/,
  uncited raw telemetry rotates after 90 days; retrieval is the slice plus a bounded episodic
  digest; provenance is sources, Node-Change trailers, node digests and invocation ids.
implementation: |-
  Partly, Stage 1 (agent-os#116): the Node-Change trailer and its check, agent_os/product/tree/trailers.py
  (`agent-os-tree trailers`, run by templates/ci-host.yml). Evidence copying, retrieval and the other
  provenance still to come.
---
What Agentos learns over months is kept in the strongest form it fits, found again where
it is needed, and never cut from where it came from.
