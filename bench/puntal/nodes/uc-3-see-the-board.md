# Node UC-3: see the board

## Ancestor goals
- G1 (global goal): anyone on the team can report a problem in under a minute and trust that it will
  not be lost.
- FR-3 (functional requirement, under G1): the whole state of the helpdesk is visible at a glance,
  and what is shown is what is stored.

## Use case
Someone opens the board. Nothing is written.

Read every ticket of the collection `tickets` and list them in ascending ticket number. Count the
statuses from the tickets you read, not from the derived document.

Answer with exactly
`{"tickets": [{"id": "T-1", "title": "...", "priority": "...", "status": "..."}],
"counts": {"open": a, "in_progress": b, "resolved": c, "total": n}}`, `tickets` empty on an empty board.
