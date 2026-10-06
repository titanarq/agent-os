---
id: dec-drift-is-judged-at-every-step-and-audited-over-time
type: decision
title: Drift is judged at every step and audited over time
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal B (faithful to its owner's goals over months)
- Owner design discussion of 2026-10-05/06, point 4 (the custodian decides whether a rollback needs the owner) and point 5 (that discretion follows its record)
premises:
- 'Over a long chain of dependent steps errors compound unless each step is checked: at 99% per step, a thousand steps succeed together about 0.004% of the time'
- Some drift only shows across many steps, which no single pull request reveals
rejected_alternatives:
- option: Audit drift only periodically
  reason: 'Implied by the first premise, not argued at approval: a periodic audit alone lets an error compound between audits'
  basis: implied
- option: Every rollback goes to the owner
  reason: 'The owner: the custodian decides whether a rollback merits the owner''s review; there is no default'
  basis: stated
review_triggers:
- Drift is found that both the per-pull-request judgment and the periodic audit missed
---
Every pull request of a branch is judged against the branch's goals and use cases. Each implemented
or hardened node is a checkpoint, and a rollback returns to the last good one. The custodian audits
the whole tree periodically and decides whether a rollback needs the owner, a discretion that follows
its record. Rework that does not decay, and high unverified exposure, trigger experiments instead of
retries.
