"""Question sessions (Stage 1 of `docs/AGENTOS_V2_PLAN.md`): the judgments log, the session issue
the owner answers, the write-back of an answer into its node, and the guard that keeps a change to
the what out of automatic merging.

- `judgments` -- what an agent decided alone, and what later came of it.
- `batch`, `render` -- the frozen set of questions of one session, as an issue body.
- `reply` -- the owner's answers, parsed from the grammar `docs/adr/` fixes.
- `writeback` -- an answer into its node; a reclaim into a new `what` question.
- `what_guard`, `transcription` -- a pull request that touches the owner's what, and a check that
  one transcribes a session answer exactly.
"""
