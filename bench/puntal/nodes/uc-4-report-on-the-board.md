---
reads:
  - list tickets
---
# Node UC-4: report on the board

## Ancestor goals
- G1 (global goal): anyone on the team can report a problem in under a minute and trust that it will
  not be lost.
- FR-3 (functional requirement, under G1): the whole state of the helpdesk is visible at a glance,
  and what is shown is what is stored.

## Use case
Someone asks where things stand. Nothing is written.

Read every ticket of the collection `tickets` and work out, from the tickets themselves: how many
there are in total and in each status; the oldest unresolved ticket (the lowest ticket number whose
status is not `resolved`, or null when there is none); and the unresolved tickets whose priority is
`high`, in ascending ticket number.

Answer with exactly
`{"total": n, "counts": {"open": a, "in_progress": b, "resolved": c}, "oldest_unresolved": "T-<number>",
"high_priority_unresolved": ["T-<number>"]}`.
