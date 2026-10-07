# A v2 host dispatches by node address, dependencies first and never on the same code

- Date: 2026-10-07
- Status: accepted
- Modules: product/dispatch, guard, worker driver, config, docs
- Implements agent-os#117 (Stage 1 of `docs/AGENTOS_V2_PLAN.md`);
  `docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`,
  `docs/tree/dec-tests-harden-they-do-not-build.md`

## Context
`compile` renders tickets from a product tree; until now nothing downstream read what made them
different from a hand-written issue. The founding decision says the planner never runs two tickets on
the same code at once and orders them by their dependencies, and the plan says that in a v2 host the
planner dispatches only tickets that carry a node address. A rule that lives in the planner's prompt
is forgotten (the planner already has a cap and a module exclusion enforced by the driver for this
reason, `2026-09-15-parallelism-is-a-configured-cap-enforced-by-the-driver.md`), and two things had to
be decided: what a v2 host is, and what "the same code" means when a node carries no list of files.

## Decision
- **A v2 host says so: `tree.dispatch_by_node: true`.** Not "has a tree directory": `tree.root` has a
  default and `config.example.yaml` documents it, so a host that merely copied the example would
  become v2 and every hand-written issue in its backlog would stop being dispatchable. A boolean is
  one reviewed line in the host's config, off by default, and `git subtree pull` changes nothing
  until it is set.
- **The ticket carries what dispatch reads, as marker lines**, the way `<!-- budget: -->` already
  does: `<!-- node: <id> -->` (the address), `<!-- depends-on: <ids> -->` (the node's `depends_on`)
  and `<!-- touches: <paths> -->` (the code). A body is the only thing that survives in the tracker,
  and a marker is greppable and a comment, so it needs no label, no field and no new state. The
  reader and the writer live in one file (`agent_os/product/dispatch/markers.py`).
- **Dependencies first is "no open ticket for a node it depends on".** The tickets of dependencies
  are issues like any other; once they close, the dependent is free. The guard leaves a blocked
  ticket out of the dispatchable set (the planner is not even woken for it), and the start gate
  refuses it again at the moment of dispatch. A dependency that has no ticket (a node already built,
  or one that is a container) blocks nothing.
- **"The same code" is path overlap, from the paths the node names.** The tree has no component
  records yet (`docs/tree/dec-a-component-has-a-core-and-extensions.md` decides them, nothing
  implements them), so the touched code is the paths named in a node's `implementation` and, once
  written, its `mechanism`; a directory covers what is under it. A node that names no path collides
  with nothing: the comparison cannot know what the node does not say, and refusing everything on the
  strength of nothing would stall a fresh tree, whose nodes all start with no implementation. Worker
  write-back of `implementation` is what makes the rule bite from the second ticket on, and the
  components' paths join the same set when they exist.
- **The collision is the driver's, the dependency order also the guard's.** What is running is known
  to `worker_task.sh start`, which already refuses on the cap and the module label, so the collision
  check sits next to them (`python -m agent_os.product.dispatch start-gate`) and is silent outside a
  v2 host. The scan has no running set, so it filters on address and dependencies only.
- **A ticket builds and never hardens.** Its definition of done leaves the node `implemented`;
  hardening is later work, ordered by use, and the ticket says why a node cannot be hardened yet
  when `hardening_blockers` finds something. `compile` therefore dispatches without any verification:
  the escalation `missing-verification` is gone, and a node with no verification is accepted by an
  agent's judgment.
- **The worker's brief carries the slice, cut at dispatch.** `agent_os.issues brief` appends
  `agent-os-tree context` for the ticket's node, so the worker reads its chain and never the tree,
  and a node that changed since the ticket was compiled reaches it as it is now.

## Alternatives rejected
- **A v2 host is one whose `tree.root` is set.** Rejected: see above, the example documents it.
- **A GitHub label for the address and dependencies.** Rejected: a label has no payload (which node,
  which paths) and every ticket would need two writes; the body is already the contract.
- **Refuse any ticket whose node names no code while another runs.** Rejected: it serialises a fresh
  tree entirely, which is the cost the founding decision wants to avoid.
- **Leave the check in the planner's prompt.** Rejected for the reason the cap is in the driver.

## Review triggers
- Two tickets that the rule let run together conflict in the same code.
- Nodes routinely start with no implementation, so the collision check rarely has paths to compare.
- A host needs the address rule without the collision rule, or the reverse.
