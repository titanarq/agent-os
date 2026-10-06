---
id: dec-retirement-is-a-relative-candidacy-the-owner-decides
type: decision
title: Lack of use only makes a part a candidate for retirement, and the owner decides
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal A (a usable product early, grown by real use)
premises:
- A part left for the end is not unused, it is not a priority
- Defined parts nobody uses do not get in the way
- Retiring a part changes what the product does, which is the owner's
rejected_alternatives:
- option: Retire automatically after a fixed time without use
  reason: Time without use is relative to the use of the rest of the product
  basis: stated
review_triggers:
- Unused parts that were kept get in the way of a change
---
A part is a candidate for retirement when it has been available and unused for a configured number
of days on which the rest of its branch was used (a cycle is a day with use, whatever its source;
default 10, tuned with data). Candidates reach the owner in a question session; only the owner
retires a part, and a definition is never deleted for lack of use.
