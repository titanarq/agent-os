# A node without a verification is accepted by its description and its ancestors' acceptance

- Date: 2026-10-08
- Status: accepted
- Modules: `agent_os/product/dispatch/ticket_body.py`
- Plan: `docs/AGENTOS_V2_PLAN.md`, Stage 1; `docs/tree/dec-tests-harden-they-do-not-build.md`,
  `docs/tree/dec-top-down-acceptance-is-essential-even-when-judged.md`,
  `docs/tree/fr-a-usable-product-exists-early.md`

## Context
`compile` dispatches a leaf with no `verification`: dispatch no longer requires one, and nothing waits
for a complete specification. Such a ticket's acceptance criterion was one sentence -- the node "does
what its description says and breaks no criterion of its ancestors listed under Context" -- which sends
the reader elsewhere for everything it could be judged against. Two honest ways out: refuse to compile
the ticket with a clear defect, or put into the criterion what an agent can judge against.

## Decision
The ticket is not refused. Its acceptance criteria are derived: `judged by an agent: <node> does what
its description says (the Objective above)` -- the validator's rule for a node with none, in
`prompts/validator.md` -- and then, for each ancestor from the nearest to the goal, one line per
criterion that ancestor carries, `judged by an agent: with <node> built, <ancestor> still holds:
<criterion>`. A goal always has at least one evaluator (`goal-without-evaluators`), and `compile`
refuses a tree the doctor finds anything in, so the derived list is never empty of content.

## Consequences
- Refusing would have made a node wait for a specification nobody has validated yet, which
  `dec-tests-harden-they-do-not-build` removed, and would have contradicted the validator's own rule and
  the expert's "write a verification whenever you can".
- A node under ancestors whose evaluators are all end-to-end gets criteria no single node can settle;
  the agent judging them says "still holds" or not by reading what the node adds, as the validator
  already does for every pull request of a branch. If that proves too loose, the answer is a
  verification written on the node, not a refusal at compile time.
