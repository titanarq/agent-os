---
id: dec-top-down-acceptance-is-essential-even-when-judged
type: decision
title: The top-down acceptance is essential and always holds, even when an agent judges it
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal A (a usable product early, grown by real use)
premises:
- The goals and use cases are the owner's what, so they are the criterion every branch is held to
- Whether a branch meets its goals cannot always be checked deterministically
- Deterministic tests come after use (dec-tests-harden-they-do-not-build), so something else must hold from the first build
rejected_alternatives:
- option: Only deterministic tests count as acceptance
  reason: 'The owner: the essential top-down tests may be non-deterministic, with an agent deciding whether what was built meets the goals and use cases'
  basis: stated
review_triggers:
- The judge's verdicts disagree with the owner's in test sessions more often than they agree
- A branch passes the judge and the owner rejects it, more than once
---
For every branch, an agent judges whether what was built meets the branch's goals and use cases, as
the owner wrote them: the validator on every pull request of the branch, as a merge condition and in
a context separate from the builder's, and the custodian periodically over the whole tree. A node's
verification is either a command or a criterion an agent judges. The judge's verdicts are
calibrated against the owner's in test sessions; a disagreement goes to a question session.
