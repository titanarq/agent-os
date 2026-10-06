---
id: dec-tests-harden-they-do-not-build
type: decision
title: Tests harden; they are not a requirement to build
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal A (a usable product early, grown by real use)
premises:
- 'Use validates first: as soon as feedback and telemetry arrive, the product is being tested'
- Writing tests before use asks for a specification nobody has validated yet
- The essential top-down acceptance (dec-top-down-acceptance-is-essential-even-when-judged) holds from the first build
rejected_alternatives:
- option: No dispatch without an executable verification (docs/AGENTOS_V2_PLAN.md as approved on 2026-10-04, and Phase 1's compile)
  reason: The owner prefers validating with use first and with tests after; tests are for hardening
  basis: stated
- option: The expert writes the verification of foundation nodes before a worker touches them (agreed on 2026-10-06, point 7)
  reason: 'Revised the same day under this decision: foundations get the essential acceptance and the owner''s acceptance in the first test session, and their tests later'
  basis: stated
review_triggers:
- Code validated only by use regresses, more than once, in a way a test written first would have caught
---
An action goes through three steps. **Improvised**: a puntal serves it, and the owner's acceptance
in use hardens its specification (the accepted interactions are kept as evidence). **Implemented**:
deterministic code is built from that accepted specification with no tests first; it must pass the
branch's essential top-down acceptance and then the owner's use. **Hardened**: tests are written
from the accepted interactions and coverage consolidates, never blocking use. The tree format gains
the state `implemented` between `improvised` and `hardened`, and dispatch no longer requires an
executable verification. Foundations follow the same rule.
