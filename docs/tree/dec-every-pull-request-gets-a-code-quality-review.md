---
id: dec-every-pull-request-gets-a-code-quality-review
type: decision
title: Every pull request gets a code-quality review
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06
premises:
- Small files and folders organized in depth mean every agent reads a small piece of code, which is the v2 philosophy of contained context
- Agents tend to leave flat folders with dozens of files, which nobody can navigate
rejected_alternatives:
- option: Absolute limits applied to the whole repository at once
  reason: agent-os itself has files of three thousand lines; a ratchet improves without blocking every pull request
  basis: stated
review_triggers:
- The ratchet blocks a change that a reviewer agrees made the code clearer
- Files stay over the limit for months because nobody touches them
---
Every pull request, in products and in agent-os, gets two checks. Deterministic ones in CI, as a
ratchet and blocking: new files comply and touched ones never get worse -- at most a configured
number of entries per folder and of lines per file (defaults 12 and 300). And a review an agent
makes of the diff: SOLID principles, long self-explanatory names of variables and methods, comments
only for a non-obvious why. The review requests changes the way the validator does.
