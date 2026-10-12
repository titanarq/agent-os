# A use case that an amendment contradicts is consolidated into one definition

- Date: 2026-10-12
- Status: accepted
- Modules: product tree, use cases, tests
- Tree: `docs/tree/dec-tests-harden-they-do-not-build.md`

## Context
The owner amends a use case after trying it. Each amendment lands as a patch on what was already written, so a
use case ends up as the original definition plus a trail of corrections, some of which contradict or qualify
earlier lines. It stops reading as one definition; the next agent has to replay the history to learn what is
true now. The tests written against the old lines stay, and some of them now enforce what the owner withdrew.
What was tried and failed is lost or lives only in the amendment trail, so it gets tried again.

## Decision
1. **Trigger.** Consolidation runs when an amendment arrives that contradicts or qualifies what the use case
   already says, right after the last decision of that amendment is settled. An amendment that only adds is not
   a trigger.
2. **Probado y descartado.** Every use case ends with a section of that name: what was tried and why it failed.
   No date, no author. A line is deleted when it stops being true; the consolidation prunes the section.
3. **Obsolete tests.** The consolidator proposes, in the same pull request, deleting or adjusting the tests the
   new definition makes obsolete, each with the line of the old definition that justified it. The pull request
   goes through the ordinary code-quality review.
4. **Who writes it.** Sonnet drafts the consolidated definition and Opus reviews the draft before the pull
   request is opened. One pull request per use case, holding only that case and its dependencies.

## Consequences
- A use case reads as one definition at all times; the history is in git, not in the text.
- A test is removed only with a written reason a reviewer can check, which keeps
  `dec-tests-harden-they-do-not-build` intact: consolidation never adds tests.
- Each consolidation costs one Sonnet draft and one Opus review; the trigger keeps that cost proportional to
  how often the owner changes his mind.
- "Probado y descartado" needs upkeep: a stale line misleads, so the consolidation must re-check each one.

## Alternatives rejected
- **Consolidate on a clock or at N amendments:** rewrites stable cases for nothing, and waits too long on
  unstable ones.
- **Keep an amendment log in the case:** that is the patch trail again.
- **Delete obsolete tests silently, or leave them:** the first loses the reason, the second keeps enforcing
  withdrawn behavior.
- **One pull request for all cases:** unreviewable, and one disputed case blocks the rest.
