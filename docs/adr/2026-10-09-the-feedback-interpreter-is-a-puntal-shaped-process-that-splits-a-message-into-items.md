# The feedback interpreter is a puntal-shaped process that splits a message into items

- Date: 2026-10-09
- Status: accepted
- Modules: `agent_os/product/interpreter/`, `prompts/interpreter.md`, `bin/interpreter_task.sh`, `agent_os/product/config.py`
- Tree: `docs/tree/fr-the-owner-is-asked-only-in-sessions-they-open.md`, `docs/tree/dec-a-test-session-happens-inside-the-app.md`, `docs/tree/dec-puntales-run-as-headless-processes.md`, `docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md`, `docs/tree/dec-a-soft-product-decision-is-the-refiners-and-a-hard-one-the-owners.md`, `docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`, `docs/tree/dec-one-backend-claude-code-with-opus-at-the-top.md`

## Context
The owner of the first host tried a session and sent one comment that mixed five changes of different
kinds. They then decided the comment box is a chat with the agent that interprets it, where the agent
asks its doubts, and that feedback becomes work "directly, except decisions". Every v2 product has a
test session, so the interpreter is Agentos's, and the host only paints the chat and stores the thread.

## Decision
- A process invoked like a puntal: one headless run per message, ONE model turn with no tool, JSON out
  validated by code, at most one retry with the rejection reasons, then a clean error. It reuses the
  puntal's turn runner, stream observer, outcome classification and telemetry record by building the
  puntal's `Options` (its executor and persistence fields neutral), instead of copying the driver.
- It is stateless: the host passes the thread, the case and the items so far each time.
- Output: a short `reply` that confirms what was understood or asks ONE concrete question
  (`needs_answer`), and the items the message adds or corrects. A message with several things is
  split into several items. `kind` is `change` (launched directly), `decision` (changes the what: the
  owner confirms it at the start of the next session, never built before) or `question_of_what` (open).
- Ids are assigned by code, not by the model; a correction repeats an id; `withdrawn` retracts one.
- Failure is part of the contract: one envelope on stdout always, `reply: null` on any outcome other
  than `ok`, so the host shows "could not interpret, noted" and loses nothing.
- Config: class `interpreter` (`role: interpreter`, Sonnet 5.5 like the other roles but the refiner and
  the expert) and an `interpreter:` section (reply language, timeout, effort, thread window).
  `PuntalConfig` moved from `agent_os/lib.py` to `agent_os/product/config.py` beside the new
  `InterpreterConfig`, so the oversized `lib.py` shrinks instead of growing.

## Consequences
The interpreter decides `change` versus `decision` itself, on its prompt's rule; when unsure it asks.
A wrong `change` costs a revertible pull request; a wrong `decision` costs one confirmation, so the
prompt leans to asking. Telemetry of both is in the puntal's file, and the owner's reversal of an
interpretation is the signal to tune the prompt (`dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check`).
