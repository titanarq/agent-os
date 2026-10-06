---
id: dec-a-test-session-happens-inside-the-app
type: decision
title: A test session happens inside the product's app
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal C (the owner decides what; Agentos decides how)
- Owner design discussion of 2026-10-06, point 7, question 1
premises:
- A puntal's questions are best answered in the context of the action that raised them
- Trying what changed is using the product, and any use is also a test
rejected_alternatives:
- option: A test session as a checklist outside the app
  reason: The owner chose the session inside the app
  basis: stated
review_triggers:
- A product cannot host a session mode in its own interface
---
The owner opens a test session for a branch inside the app: it shows what changed since the last
session and the cases to try, ordered by exposure, and its puntals ask their pending questions in
context -- the only place where the product asks the owner something in real time. What the owner
accepts hardens the specification; what the owner rejects returns as rework or as a question of
what; the answers are written back into the nodes.
