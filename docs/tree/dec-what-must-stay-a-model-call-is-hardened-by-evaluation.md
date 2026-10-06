---
id: dec-what-must-stay-a-model-call-is-hardened-by-evaluation
type: decision
title: What must stay a model call is hardened by an evaluation
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal A (a usable product early, grown by real use)
- Owner design discussion of 2026-10-05, point 1, question 2
premises:
- Some actions genuinely need a language model, and the product should not pretend otherwise
- Without a marker the determinism ratio would count them as unfinished work
rejected_alternatives:
- option: Count a part that must stay a model call as improvised forever
  reason: The owner chose that it can be hardened as such
  basis: stated
review_triggers:
- An llm_by_design part passes its evaluation while the owner rejects its answers
---
A part that must stay a model call is hardened with `llm_by_design: true`: a narrow prompt verified by
an evaluation over accepted examples with a pass threshold. An LLM judge is used only where a property
cannot be checked mechanically, and its accuracy is calibrated against the owner's verdicts.
