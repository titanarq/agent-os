---
id: dec-a-change-to-the-what-is-merged-only-on-the-owners-word
type: decision
title: A change to the what is merged only on the owner's word
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal B (faithful to its owner's goals over months)
- Owner design discussion of 2026-10-06, point 6 (changing the evaluator counts as what)
premises:
- Goals and their evaluators are the owner's; the evaluators are what ultimately watches over the goals
- An answer the owner gave in a question session is already the owner's decision
rejected_alternatives:
- option: An agent changes a goal or an evaluator when the evidence supports it
  reason: Evidence settles how, never what; a method allowed to change its evaluator learns to approve itself
  basis: stated
- option: The owner merges by hand every pull request that writes back an answer
  reason: 'The owner: an answer in a question session counts as approval'
  basis: stated
review_triggers:
- A change to the what reaches main without the owner's word
- The owner rejects, after the merge, a pull request that transcribed an answer
---
A pull request that touches a goal node or an evaluator -- a goal's verification, the composition of
the method battery, the thresholds of the indicators, the rule that tells what from how -- is never
merged automatically. It is merged on the owner's word: the owner's own merge, or an answer the owner
gave in a question session, which the validator checks the pull request transcribes exactly.
