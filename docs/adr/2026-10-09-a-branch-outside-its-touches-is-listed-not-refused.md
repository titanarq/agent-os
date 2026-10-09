# A branch that changes files outside its ticket's `touches` is listed, not refused

- Date: 2026-10-09
- Status: accepted
- Modules: `agent_os/product/tracker/paths_outside_touches.py`, `bin/worker_task.sh` (`open-pr`), `prompts/validator.md`
- Plan: `docs/AGENTOS_V2_PLAN.md`, Stage 1; `docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`, `docs/tree/fr-independent-work-runs-in-parallel.md`

## Context
Dispatch lets two tickets run at once because the paths each declares in `touches` do not overlap.
That is the whole premise of running work in parallel without conflicts. In the first v2 host, two
workers (#33 and #34) changed files beyond their ticket's `touches` -- refactors that were reasonable
on their own -- and #33 collided with #39, which was running in parallel on exactly those files. The
gate had nothing to see: the declaration was honoured by the gate and not by the worker.

## Decision
`open-pr` does not refuse such a branch. It lists, in the body of the pull request it opens, every
file the branch changes that no declared path covers (a directory covers what is under it; the node
files under `tree.root` are the worker's own write-back and are not listed). The validator judges each
listed file -- justified or not -- and says whether it could collide with a ticket running in
parallel, reading the `touches` of the tickets in `status:doing`. An unjustified file is a request for
changes; a justified one that overlaps a running ticket goes to the human in `## Doubts`.

It is not refused because a refactor beyond the declared paths is often the right call, and a
mechanical refusal at the end of a finished run spends the run: the diary and the trailers are
refused because the pull request would be wrong whatever anyone judged, and this one is a judgement
(is the file the ticket's business?) that a deterministic check cannot make. What was missing was not a
barrier but visibility at the one place a reviewer already looks, before the merge.

## Consequences
- Nothing is blocked, pushed late or relabelled over it: a ticket with no `touches` marker (a host
  whose tickets do not come from a tree) or a branch inside its paths gets the pull request it always
  got. A diff git cannot read opens the pull request without the section and says why on the driver's
  output: a failure of the tool is no verdict.
- The section is written when the pull request is created. A pull request that already exists keeps
  the body it was created with; a resumed worker that grows beyond its `touches` in a later round is
  seen by the validator through its own diff.
- The listing is measured from the merge-base with the base (a three-dot diff), so the base's own
  commits never appear in it.
- If the listing proves noisy (tests of the touched code are always listed when `touches` names only
  source paths), the answer is a better `touches` from whoever writes the node, not a looser check.
