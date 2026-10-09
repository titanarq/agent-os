# A chat test session is ingested directly, except decisions, and its result is left for the next session

Date: 2026-10-09. Amends `2026-10-09-a-closed-test-session-is-ingested-by-a-command-that-plans-first.md` (its points 4 and 8:
what a verdict becomes, and the reader per schema). Tree: `docs/tree/uc-open-a-test-session-for-a-branch.md` (mechanism,
"What becomes of the feedback"), `dec-a-test-session-happens-inside-the-app` (the owner's word: "Directo, salvo decisiones"),
`fr-the-owner-is-asked-only-in-sessions-they-open`, `dec-a-change-to-the-what-is-merged-only-on-the-owners-word`,
`dec-a-soft-product-decision-is-the-refiners-and-a-hard-one-the-owners`, `dec-a-question-session-is-a-github-issue`,
`dec-tests-harden-they-do-not-build`, `dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check`.

## Context

The first host now writes the session file in schema 2: the owner's comment box is a chat, `comments[]` holds the thread
(`role` owner or agent, `text`, `state`, `case`, `page`, `at`), `cases[].verdict` is `perfect`, `ok_with_improvements`,
`needs_work` or `not_tried`, and, once the feedback interpreter is connected (`docs/FEEDBACK_INTERPRETER.md`), `items[]`
holds what it understood: `change`, `decision` or `question_of_what`, each with the `from_messages` it came from and a
`withdrawn` flag. Sessions closed before the interpreter was connected carry no `items` at all, and the owner is testing
that way today. The reader of the first ADR named and skipped such a file.

## Decision

1. **One reader per schema, now two.** Schema 2 is read by its own parser (`session_ingest/chat/`); schema 1 is untouched
   and keeps its meaning (`accept`/`reject`/`not_tried`, a note per case). A schema the reader does not know is still named
   and left pending. Every key is checked: a state, a verdict or an item kind outside the contract, or a `from_messages`
   position outside the thread, names the file and skips it.
2. **The feedback is split, and launched directly, except decisions** (the owner's word):
   a `change` that is not withdrawn becomes **one issue per item**, in the shape of the rework ticket of the first ADR
   (the seven sections validated before anything is written, `<!-- node: -->` when the item has a node, the budget class,
   the interpreter's reading **and** the owner's messages it came from, quoted whole and defused, and a
   `<!-- key: test-change.<session>.item.<id> -->` line for idempotency); a `decision` **is not launched**; a
   `question_of_what` **is not launched**; a withdrawn item is nothing. A decision changes the what, and a change of the
   what is merged only on the owner's word (`dec-a-change-to-the-what-is-merged-only-on-the-owners-word`); whether it is
   soft (the refiner's) or hard (the owner's) is a derived hardness that this command has no business computing from free
   text (`dec-a-soft-product-decision-is-the-refiners-and-a-hard-one-the-owners`).
3. **A `question_of_what` does not become a question-session issue.** A question session freezes questions that are recorded
   on nodes, each with its default answer, and writes the reply back into its node (`dec-a-question-session-is-a-github-issue`).
   An item has no default answer and may have no node; recording it on a node would be an edit of the what that nobody
   authorised, and inventing a default would put the command's words in the owner's mouth. It is kept as an open question
   for the next test session, the one place where the owner is asked in real time (`fr-the-owner-is-asked-only-in-sessions-they-open`);
   the plan says so line by line. If the host or the expert later records it as a node question, the question session takes it.
4. **What no item covers is never lost.** An owner message that no item names in `from_messages` (a session with no `items`,
   `items: []` because the interpreter failed on every message, a message it could not read) is handled by the last state of
   its case, and the thread of the case, both roles, is quoted: `needs_work` is rework (the key and the ticket of the first
   ADR, `test-rework.<session>.<node>`); `ok_with_improvements`, or a state-less remark on a case, is a change with the thread
   quoted (`test-change.<session>.case.<node>`); a comment on no case is **one general change** that says no interpreter read
   it (`test-change.<session>.general`); a state alone, with no text, names no change and is only said in the plan. Text
   that an item names, even a withdrawn one, is not repeated: the interpreter already read it, and a withdrawn item is the
   owner's retraction. A session without `items` is therefore the same algorithm with nothing covered, not a second one.
5. **`perfect` is the owner's acceptance**, as an `accept` was: `acceptances: [{session, date}]` on the node, once per session
   (`dec-tests-harden-they-do-not-build`: the owner's acceptance in use hardens the specification). The last state of the case
   wins; the text of a `perfect` comment is not turned into work.
6. **"What I understood and where it went" is a file Agentos writes and the app reads**:
   `<tree.test_sessions_dir>/understood.json` (contract in `docs/AGENT_OS.md` §4.11), one block per ingested session with the
   decisions to confirm, the open questions and the changes launched with their issues. It is in the sessions directory because
   that is the one place both sides already share and configure; the session reader skips it by name, and the host's reader
   (`ts-*.json`) never sees it. Agentos is the only writer, whole file by atomic replace, one block per session (a second
   ingestion replaces the block, so it is idempotent by effect); a damaged file refuses the run before any effect and is never
   overwritten by guess. A session that left nothing to show writes no block.
7. **Plan by default, `--apply` to act, idempotent by effect** as in the first ADR. Answers of schema 2 are the same edit as
   schema 1 (`writeback.answer_question`) and the tree edits stay in the working tree for a worker to carry on a pull request
   marked `Test-Session: <id>`; the file for the app is not part of the tree and is not committed.

## Rejected alternatives

- *Launch decisions too, flagged.* Against the owner's word, and against the rule that the what changes only on the owner's word.
- *A question-session issue per `question_of_what`.* See 3: it needs a node question and a default the item does not have.
- *Rework or change by the state of the case even when items exist.* It would launch the same work twice, once as the item and
  once as the case; the item is the finer reading, so what an item covers is left to it.
- *One file per session for the app.* The app would have to know which to read; a single file with a block per session is
  what "when the next session opens" asks for, and the block says which session it belongs to.
- *Writing the file in the tree.* It is a view for the app and not a requirement; a pull request per ingestion would be bookkeeping.

## Review triggers

The interpreter's items stop pointing at the right messages (a `from_messages` that does not match what the ticket quotes);
the owner confirms decisions in the next session and nothing turns the confirmation into a change of the what (the step after
this one: the owner's word on a decision becomes a tree edit through the validator of `dec-a-change-to-the-what-is-merged-only-on-the-owners-word`);
the app needs the file to say a decision was already shown; a host whose sessions directory cannot hold a file of Agentos.
