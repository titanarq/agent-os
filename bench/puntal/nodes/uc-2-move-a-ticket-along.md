# Node UC-2: move a ticket along its life

## Ancestor goals
- G1 (global goal): anyone on the team can report a problem in under a minute and trust that it will
  not be lost.
- FR-2 (functional requirement, under G1): a ticket's status only ever moves forward, and says what
  happened when it ends.

## Use case
Someone moves a ticket to its next status. Payload: `id` (`T-<number>`), `status` (the status asked
for) and `note` (free text, only for `resolved`).

The life of a ticket is `open`, then `in_progress`, then `resolved`. Nothing is skipped, nothing goes
back, and `resolved` is final. A ticket becomes `resolved` only with a non-empty `note`.

1. Read the ticket. Refuse when it does not exist, when `status` is not the very next status of its
   life, or when it would become `resolved` without a note. A refusal writes nothing at all.
2. Otherwise update the ticket: its new `status`, and `resolution` set to the note exactly as given
   (trimmed) when it becomes `resolved`, left `null` otherwise.
3. Keep the derived document `summary/board` true: after your write, recount ALL tickets of the
   collection and store `{"open": a, "in_progress": b, "resolved": c, "total": n}`.

Answer with exactly `{"ok": true, "ticket_id": "T-<number>", "status": "<the new status>"}`, or on a
refusal `{"ok": false, "ticket_id": "T-<number>", "reason": "<one short sentence>"}`.
