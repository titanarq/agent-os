---
id: dec-a-question-session-is-a-github-issue
type: decision
title: A question session is one GitHub issue, opened by the owner
state: in-force
decided: 2026-10-06
sources:
  - "Owner design discussion of 2026-10-06, doubt 3 of the how pass (option 1, accepted as described)"
premises:
  - "The substrate already writes a question to the owner in their language and in functional terms, and the owner's reply wakes the planner (docs/adr/2026-09-15-a-question-for-the-human-is-written-in-their-language-and-in-functional-terms.md, docs/adr/2026-09-14-a-humans-reply-wakes-the-planner-never-the-worker-that-asked.md)"
  - "Method proposals and changes to the tree are already pull requests, which an issue can link"
  - "Nothing waits on the owner in real time outside a session the owner opens"
rejected_alternatives:
  - option: "Question sessions inside the product's own app, like test sessions"
    reason: "Questions about Agentos would be tied to one product's interface, and every product would have to build it"
    basis: stated
  - option: "A generated page per session"
    reason: "The owner's answers would need a write channel that does not exist"
    basis: stated
review_triggers:
  - "The owner stops opening question sessions while questions accumulate"
  - "A session's questions do not fit one issue the owner can answer in one sitting"
---
The progress board shows how many questions are pending per branch. When the owner chooses -- a
label, or asking for it -- a session opens: one GitHub issue freezes the batch, with the questions
numbered, grouped by branch, ordered by what they block, and each carrying its default answer. The
owner answers only the ones they want ("1: yes; 3: no, rather X"); the reply wakes the planner, and
each answer is written back into its node. A question left unanswered keeps its default, stays
open and comes back in the next session. Questions reach the expert before they reach this issue.
