---
id: dec-a-goal-without-evaluators-is-a-red-check
type: decision
title: A goal without evaluators is a red check
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal B (faithful to its owner's goals over months)
premises:
- The top-down acceptance is essential (dec-top-down-acceptance-is-essential-even-when-judged), and it needs a criterion for every goal
- A criterion an agent judges can be written in a sentence, so an evaluator never has to wait for data or code
rejected_alternatives:
- option: Evaluators optional on a goal
  reason: A goal nothing evaluates cannot keep the work below it from drifting
  basis: stated
review_triggers:
- The owner needs to record a goal before being able to say how it is evaluated, more than once
---
A goal's `verification` holds its evaluators -- commands, or criteria an agent judges -- and the tree
doctor fails on a goal that has none, the way it fails on any other broken rule.
