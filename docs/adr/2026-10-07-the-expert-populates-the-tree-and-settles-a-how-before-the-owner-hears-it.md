# The expert populates the tree and settles a how before the owner hears it

- Date: 2026-10-07
- Status: accepted
- Modules: `prompts/expert.md`, `bin/agent_task.sh`, `agent_os/lib.py`, `agent_os/guard.py`
- Plan: `docs/AGENTOS_V2_PLAN.md`, Stage 1; issue #118

## Context
Stage 1 needs someone to turn the owner's goals into small requirement and use-case nodes, to record
what is not known before anything is built on it, and to read every question before the owner does
(`docs/tree/dec-a-doubt-of-how-is-settled-by-an-experiment.md`,
`docs/tree/dec-a-challenge-is-flagged-early-and-the-owner-decides.md`). The validator and the
refiner are one-shot role drivers; the open points were what the expert writes, where, how it is
launched, and which `Node-Change` value its commits carry.

## Decision
1. The expert is a one-shot role under `agent_task.sh`, with a class of its own (`role: expert`,
   Sonnet) and the App `project.role_apps.expert`, else the planner's. Unlike the refiner it WRITES:
   the driver makes a throwaway worktree off the host's default branch (fetched, resolved by name),
   starts the backend inside it, and the expert commits on `expert/<N>-<slug>`, pushes and opens one
   pull request. It never merges. The worktree is removed when the run ends, so whatever is not
   pushed is lost.
2. It writes only under the tree root, never a goal or an evaluator, never a decision. A goal with
   no evaluator, or two goals that contradict, reach the owner as a `what` question, not as an edit.
3. A question reaches it first. A `how` it settles itself (`outcome: answered`, with the finding) or
   by recording an open `spike`; the owner never receives it. A `what` is recorded with its
   `default_answer` and goes to the owner in the summary comment. When it cannot tell, it is `what`.
   Every how it settled goes in a digest in the same comment, so the owner can reclaim it.
4. It records a spike, it does not run one: running it is a worker's ticket, with the timebox the
   spike names.
5. Its commits carry `Node-Change: usage` by default (a new node, or a revision driven by an answer,
   a finished spike or use) and `Node-Change: rework` only for a revision of a node an earlier pass
   of its own wrote wrongly; never `owner`, which is for commits carrying the owner's own words.
   Rationale: populating the tree is not rework, and counting it as such would make the symptom
   "rework that does not decay" fire on a tree that is merely being written.
6. It is launched by a command, `agent_os/bin/agent_task.sh expert <issue>`, with the issue as its
   request (a new product, a question that reached it, a part of the tree to populate). The guard
   announces its end (`expert_finished`) and reports a run that died, like the other one-shot roles,
   but nothing launches it unattended: the planner's prompt says it never does, and a died expert
   is the human's to relaunch. Launching it from a label or from the planner is a later decision.

## Consequences
- The expert's pull request touches only the tree, so it never needs the owner's word under
  `docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`; the check that a pull
  request touching a goal or an evaluator is held for the owner is a separate piece of work and the
  expert's own constraint is, today, its prompt.
- Hosts get the role with the next `git subtree pull`: add the `expert` class from
  `config.example.yaml` to `config/agents.yaml` (a host without it fails `agent_task.sh expert`
  loudly, as for any role with no class).
