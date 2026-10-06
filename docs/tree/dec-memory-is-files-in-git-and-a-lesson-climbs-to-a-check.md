---
id: dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check
type: decision
title: Memory is files in git, and a lesson climbs to the strongest form it fits
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal D (Agentos improves with every product)
- Owner design discussion of 2026-10-05, point 2 (persistent memory)
premises:
- A note was ignored at least three times while it was already written (the worktree and editable-install trap); a check is never ignored
- A memory that does not reach the context that needs it does not exist
- Provenance survives only if what is cited is kept
rejected_alternatives:
- option: GitHub issues and a GitHub Project as the memory
  reason: Issues are dispatch tickets and the episodic record of work; a Project is a view of progress and the owner's order of the backlog, nothing more
  basis: stated
- option: Forget by deleting
  reason: Deleting cuts provenance; forgetting is leaving something out of the context
  basis: stated
review_triggers:
- A lesson already recorded fails again
- Checks accumulate that never fire
---
Working memory is the slice of one call. Episodic memory is telemetry, logs, issues, pull requests
and commits with their `Node-Change` trailer; semantic memory is the tree, the ledger, the ADRs and
AGENTS.md; procedural memory is hardened code, tests, prompts and config. A lesson climbs to the
strongest form it fits: note, then rule, then executable check -- and a lesson the operator records
about the mechanism outside the repository climbs into it by a pull request. Forgetting is leaving
out of the context, never deleting what is cited: cited telemetry is copied into `evidence/`,
uncited raw telemetry rotates after 90 days. Retrieval is the slice plus a bounded episodic digest.
