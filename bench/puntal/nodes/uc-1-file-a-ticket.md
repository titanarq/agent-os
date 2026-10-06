# Node UC-1: file a ticket

## Ancestor goals
- G1 (global goal): anyone on the team can report a problem in under a minute and trust that it will
  not be lost.
- FR-1 (functional requirement, under G1): the helpdesk keeps exactly one ticket per reported problem,
  each with a stable id that is never reused.

## Use case
A team member reports a problem. Payload: `title` (what is wrong, free text) and `priority` (`low`,
`normal` or `high`; `normal` when absent).

1. Take the next ticket number from the counter named `ticket` (`next-id`). Never count tickets
   yourself. The ticket's id is `T-<number>`.
2. Store the ticket in the collection `tickets` under that id, as
   `{"id": "T-<number>", "title": <the title, trimmed, otherwise verbatim>, "priority": <priority>,
   "status": "open", "resolution": null}`.
3. Keep the derived document `summary/board` true: after your write, recount ALL tickets of the
   collection and store `{"open": a, "in_progress": b, "resolved": c, "total": n}`.

Answer with exactly `{"ok": true, "ticket_id": "T-<number>"}`.
