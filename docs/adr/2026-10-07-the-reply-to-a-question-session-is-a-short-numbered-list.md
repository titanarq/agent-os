# The reply to a question session is a short numbered list, and a bare "no" answers nothing

- Date: 2026-10-07
- Status: accepted
- Modules: `agent_os/product/sessions/` (`reply.py`, `transcription.py`)
- Plan: `docs/AGENTOS_V2_PLAN.md`, Stage 1; issue #119; `docs/tree/dec-a-question-session-is-a-github-issue.md`

## Context
The owner answers a session in a GitHub comment, in their own words and in little time. The answer
is then written into a node by a pull request that is merged on the owner's word, which only holds
if the validator can check the pull request says exactly what the owner said.

## Decision
1. An item is `N: <body>`; items are separated by `;` or a line break, and a `;` followed by
   something that is not a new item stays in the answer.
2. `yes` (also `y`, `ok`, `accept`) accepts the default. `no, rather X`, `no: X`, `no - X` and
   `no, instead X` answer X. Any other body is itself the answer. A bare `no` declines the default
   without giving another answer: nothing is written, the question stays open and returns next
   session. `yes, but X` is the answer "yes, but X", never an accepted default -- accepting a
   default with a caveat is not something a parser may guess.
3. `reclaim M` takes entry M of the digest back; it is never a question number.
4. Several owner comments are read in order; a later answer to a number replaces an earlier one.
   Comments of anyone but `project.human_login` are not read.
5. The answer is written as the node question's `finding`, character for character, so that
   `verify-answer` can compare it exactly; anything else in the diff fails the check.
6. The guard on the what is a deterministic check (`guard-what`), wired as a sixth condition of the
   control plane's merge gate and as a block of the validator prompt, not a judgment of a model.

## Consequences
- A reply in a form the grammar does not know is ignored, never half-applied; `answers N` shows what
  was understood before anything is written.
- A goal-node answer, which the guard stops, merges only by the owner's own merge or by a pull
  request `verify-answer` proves is exactly their answer.
- The frontmatter of a written-back node is re-dumped, so YAML comments inside it are lost.
