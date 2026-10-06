---
id: dec-a-v1-adr-enters-the-ledger-when-first-challenged
type: decision
title: A v1 ADR enters the ledger the first time it is challenged
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, point 1 of the global goals (2026-10-05)
premises:
- Decisions taken early with too little context harm a project when nobody questions them; everything in a development can be improved
- Migrating every ADR at once is work nobody needs until an ADR is questioned (lazy materialization)
rejected_alternatives:
- option: Migrate every docs/adr/ file into the ledger now
  reason: 'Implied by the second premise, not argued at approval: the work would be done before anyone needs it'
  basis: implied
review_triggers:
- An agent obeys an ADR whose premise no longer holds because it never entered the ledger
---
The ADRs in docs/adr/ stay where they are. The first time one is challenged, it is written into the
ledger with its premises, rejected alternatives and review triggers, and from then on it is revised
like any other decision.
