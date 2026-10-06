---
id: dec-proactive-critique-waits-for-a-second-phase
type: decision
title: Proactive critique waits for a second phase; use is the first engine of refinement
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, point 1 of the global goals (2026-10-05)
premises:
- Feedback from early use brings new premises; critique on the same premises adds little
- Proactive review of what was built is hard to do well
rejected_alternatives:
- option: Critic agents reviewing what was built from day one
  reason: The owner left it for a second phase and made use the engine of refinement
  basis: stated
review_triggers:
- A defect reaches the owner that no use could have revealed before it did harm
---
Until its trigger fires, nothing reviews what was built on its own initiative: refinement is driven by
use and feedback. The validator stays -- it verifies against declared criteria, which is not
proactive critique.
