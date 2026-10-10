"""The feedback interpreter (Agentos v2): the agent behind a test session's comment box.

The box is a CHAT (`docs/tree/dec-a-test-session-happens-inside-the-app.md`): each message the owner
sends goes here, and this answers in the same thread -- confirming what it understood or asking ONE
concrete doubt -- and leaves its reading as separate ITEMS (a change, a decision about the what, an
open question of what), each tied to a node. It is invoked as a puntal is
(`docs/tree/dec-puntales-run-as-headless-processes.md`): one headless process, ONE model turn with no
tool, JSON out validated by code; it reuses the puntal's turn runner, stream observer and telemetry
(`agent_os.product.puntal`). The host paints the chat and stores the thread and the items; this
package keeps nothing between runs. Directly "except decisions": a `change` is launched by the
ingestion, a `decision` waits for the owner's confirmation at the start of the next session
(`docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`).

- `request.py` the request and its parsing; `brief.py` the model's first message.
- `interpretation.py` + `items.py` the model's answer, validated.
- `run.py` the turn and its one retry; `options.py` config -> the puntal's `Options`.
- `envelope.py` what the host reads; `cli.py` the command line.
"""

from agent_os.product.interpreter.cli import main

__all__ = ["main"]
