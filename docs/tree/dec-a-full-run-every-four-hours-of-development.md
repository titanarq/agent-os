---
id: dec-a-full-run-every-four-hours-of-development
type: decision
title: Tests run per branch, and the whole suite every four hours of development
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06
premises:
- Running only the branch's tests keeps every pull request fast
- A coupling nobody declared is invisible to a per-branch selection
- Four hours bound how long such a coupling can go unseen
rejected_alternatives:
- option: A nightly full run
  reason: The owner chose a run every four hours of development, carried by whichever pull request is due
  basis: stated
review_triggers:
- A failure the full run finds traces back further than one interval
- Full runs keep finding nothing the per-branch selection missed
---
A pull request's CI runs the tests of its branch -- integration tests with another branch live on
both sides. When four hours of development have passed since the last full run, the next pull
request runs the whole suite; with no development, there is no run. A failure the full run finds
and the selection missed is a coupling nobody declared, and gets its integration test. This applies
to products and to agent-os.
