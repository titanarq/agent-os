# An issue from a test session keeps its task apart from its context

- Date: 2026-10-10
- Status: accepted
- Modules: session_ingest, workers
- Amends: `2026-10-09-a-chat-test-session-is-ingested-directly-except-decisions.md` (point 2: the issue quoted the
  owner's messages beside the reading)
- Tree: `docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`,
  `docs/tree/dec-a-test-session-happens-inside-the-app.md`, `docs/tree/dec-tests-harden-they-do-not-build.md`

## Context
Found in use on 2026-10-10. A host's issue made by `agent-os-sessions test-ingest` from one comment with five items put the
owner's whole message inside "Objective" -- the four decisions the owner had not confirmed among it -- and said that when
the interpreter's reading and the messages disagree "the messages are right". A worker that does what it reads builds what
is not decided: the very thing the owner's word on the what forbids. The owner: "explain clearly to the worker which
information is context and which is the task itself".

## Decision
1. **The task is the item's summary and nothing else.** `## Objective` opens "Task -- the only work this issue asks for",
   and the acceptance criterion and the stage point at "the Task", not at "the messages".
2. **The messages are background.** `## Context` opens "Context -- background, not part of the task. Nothing in this
   section asks for work." and holds the origin (session, page), the node and the owner's messages quoted whole and
   defused. They are still quoted whole, because the reading can be wrong and the worker must be able to check it, but a
   disagreement between Task and messages is said on the issue, never resolved by building more.
3. **What else the messages said is named, not hidden.** `## Not included` lists every other item, not withdrawn, that the
   interpreter read from the same messages -- changes (they have an issue of their own), decisions and questions of what
   (they wait for the owner) -- by its summary, each marked "tracked separately, NOT part of this task". The same holds for
   an issue by the state of a case or a general one, whose thread may hold messages that items cover.
4. **The headings do not change.** `agent_os.lib.REQUIRED_SECTIONS` is the validator's contract for every issue of every
   host and the refiner's prompt repeats it; a "Task" or "Context -- ..." heading would have broken both. The words are the
   first line of the section, which the worker reads as the section's name. The `budget`, `node` and `key` markers and every
   reader of the body (`section_failures`, `parse_stages`, the blockers, the judged label) are untouched.
5. **`prompts/worker.md` says it once**, in the part about the brief: in an issue from a test session the Task is the work and
   the Context is background.

## Consequences
- The rework ticket of a rejected case (`session_ingest/rework_ticket.py`) is not changed: there the owner's note is the
  task itself (make the node do what it says), not a message that holds other things.
- The summary the interpreter writes is worded as "what is wrong or wanted"; it is used as the Task as it comes. Asking the
  interpreter for an imperative would change its prompt and its golden and is left to its own task.
