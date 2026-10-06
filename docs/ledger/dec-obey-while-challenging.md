---
id: dec-obey-while-challenging
type: decision
title: Obey while challenging
state: in-force
decided: 2026-10-04
sources:
  - "docs/AGENTOS_V2_PLAN.md, 'Founding decisions' row 5 and 'Phase 2'; approved by the owner in the design discussion of 2026-10-04"
premises:
  - "Parallel workers relitigating decisions never converge"
  - "The missing piece is a cheap revocation channel, not disobedience"
rejected_alternatives:
  - option: "Free relitigation: each parallel worker may re-decide a decision in force on its own"
    reason: "The first premise argues it: parallel workers relitigating decisions never converge, and the second names the real gap as a revocation channel, not disobedience"
    basis: stated
  - option: "Obey with no challenge channel: decisions are followed and there is no cheap way to revoke one"
    reason: "Implied by the second premise, which says the revocation channel is the missing piece; not argued at approval, so no reason for rejecting it beyond that is on record"
    basis: implied
review_triggers:
  - "Challenge channel unused after 2 months"
  - "Friction telemetry never fires"
---
A decision in force is obeyed by every worker, including while it is being challenged: an
`under-review` decision binds exactly as an `in-force` one does. Disagreement goes through a cheap
revocation channel -- a challenge, and friction logged against the decision's id when a constraint
made a solution worse -- and never through a worker deciding otherwise on its own. The channel
itself is Phase 2's wiring; this decision is the rule it serves.
