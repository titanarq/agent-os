# A node may declare the code it touches, and a declaration decides

- Date: 2026-10-08
- Status: accepted
- Modules: `agent_os/product/tree/models.py` (`Node.touches`), `agent_os/product/dispatch/touched_code.py`
- Plan: `docs/AGENTOS_V2_PLAN.md`, Stage 1; `docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`

## Context
Dispatch never runs two tickets on the same code, so it compares the paths a node touches. The tree
format had no field for them: they were derived from the prose of `implementation` and `mechanism`,
taking any word with a slash or a file extension for a path. `http.client`, `p.ej` or a document named in
passing then count as code, and a ticket is held back, or collides, over something that is not its code.

## Decision
`touches:` is an optional list of paths under the host's root on a node. Present, it decides: the
ticket's `touches` marker is exactly that and the prose is not read. `[]` is present: it says the node
touches no known code (and, like any node that names none, collides with nothing). Absent, the
derivation is unchanged. An entry is one word the marker can carry (no whitespace, comma or `-->`) that
names something under the root and not the root: anything else is a `schema` defect, loud at the
doctor and not a silently inert path.

## Consequences
- No existing tree changes meaning: the field is new and absent means what it always meant.
- The worker's write-back of `implementation` no longer feeds the comparison of a node that declares
  `touches`; the declaration is the expert's or the owner's. The expert prompt does not mention the field
  yet (a prompt change regenerates its golden); it is a follow-up.
- A goal may carry the field without a defect, as it may carry `reads`; it is never a ticket.
