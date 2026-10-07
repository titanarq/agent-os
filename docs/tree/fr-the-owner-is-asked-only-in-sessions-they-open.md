---
id: fr-the-owner-is-asked-only-in-sessions-they-open
type: functional-requirement
title: What only the owner can decide reaches them in sessions they open
parent: goal-owner-decides-what-agentos-decides-how
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, points 3, 7; extends docs/AGENTOS_V2_PLAN.md
decisions:
- dec-a-question-session-is-a-github-issue
- dec-a-test-session-happens-inside-the-app
- dec-a-doubt-of-how-is-settled-by-an-experiment
mechanism: |-
  Stage 1. Two kinds of session, both opened by the owner: a test session inside the app (the only
  place where the product asks something in real time) and a question session, one GitHub issue per
  session. Questions are recorded when they arise, each with its default answer, and reach the expert
  first; a question of what blocks the hardening of its node until it is answered.
implementation: '`agent_os/product/sessions/` -- the question session issue, the reply grammar and the judgments log (`docs/AGENT_OS.md` §4.9); the test session is not built yet'
---
Nothing waits on the owner in real time. Questions are recorded when they arise and
answered in test sessions or question sessions the owner opens. A doubt about what a part
of the product is for is one of them, and until it is answered that part stays
schematic.
