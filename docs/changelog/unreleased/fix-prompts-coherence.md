- Prompts coherence (no issue; branch `fix/prompts-coherence`) -- the owner's audit of the role prompts, applied. Contradictions and
  stale lines: the planner's rework rule no longer says a rework "counts as an attempt" under a cap that counts only guard
  cuts (it spends none of `planner.relaunch_cap`; the planner counts rework stages), and a launch refused for an exhausted
  quota is the one exception to "never retry a refused `start`"; the refiner lost a Node-Change trailer block it can never
  use (it never commits) and its budget-line ordering now matches the ticket renderer; the worker lost the `QUOTA_HIT`
  line nothing reads and two host-specific remarks (`skip-worktree`, "the database"); the expert no longer promises a
  validator nobody launches. Bloat: `prompts/planner.md` 23.7K to 21.2K characters (ADR names, issue numbers and
  restated rationale out, every rule kept), the worker's liveness and subagent sections each said once, the
  validator's environment rule once. Goldens regenerated from the fixture and checked against the prompt diff.
