# The feedback interpreter

The comment box of a test session is a CHAT (`docs/tree/dec-a-test-session-happens-inside-the-app.md`,
`docs/tree/fr-the-owner-is-asked-only-in-sessions-they-open.md`). Each message the owner sends goes to
this agent, which answers in the same thread -- confirming what it understood or asking ONE concrete
doubt -- and leaves its reading as ITEMS. The host paints the chat and stores the thread and the items;
Agentos ingests the items (`agent_os/product/sessions/`). Decision: `docs/adr/2026-10-09-the-feedback-interpreter-is-a-puntal-shaped-process-that-splits-a-message-into-items.md`.

## Invoking it

```
agent_os/bin/interpreter_task.sh interpret [--request FILE|-] [--tree-root DIR] [--model M]
    [--timeout SECONDS] [--telemetry-file F] [--dry-run]
python -m agent_os.product.interpreter interpret ...        # the same, without the shell wrapper
```

One headless process per message, ONE model turn with no tool (the puntal's turn runner,
`dec-a-puntal-plans-in-one-turn-and-code-executes`), at most one retry when the answer is not a valid
interpretation. STDIN (or `--request`) is the request, STDOUT is exactly one JSON envelope whatever
happened, STDERR the diagnostics. `--dry-run` prints the system prompt and the brief and spends nothing.

## The request (JSON)

| Field | Meaning |
|---|---|
| `message` | required. The owner's new message: `text` (non-empty), `state`, `case`, `page`, `at` (all optional, free text; `state` is the host's own verdict word, e.g. `perfect`, `ok_with_improvements`, `needs_improvement`, `incorrect`). |
| `thread` | the stored messages so far, in order, each `{role: owner\|agent, text, state, case, page, at}`. Pass ALL of them in stored order: positions in `from_messages` are positions in this list, and the new message is at position `len(thread)`. |
| `case` | optional `{id, title, description, verification: [text, ...]}`. When absent and `message.case` is set, the node is read from the host's product tree (`--tree-root`, default `tree.root`); a case the tree does not have is a refusal. |
| `items` | the items already interpreted in this session (the shape below), so the model corrects instead of duplicating. |
| `session_id`, `invocation_id`, `labels` | recorded in the telemetry. `invocation_id` defaults to a UUID. |

## The envelope (stdout)

`schema` (1), `invocation_id`, `outcome`, `exit_status`, `detail`, `message_position`, `reply`,
`needs_answer`, `items`, `retries`, `cost_usd`.

- `outcome` / `exit_status`: `ok` 0, `error` 1 (the backend failed), `not_run` 2 (the request or the
  config is wrong; nothing was spent), `contract_violation` 3, `ceiling_cut` 4, `invalid_output` 5
  (not a valid interpretation after its retry), `timeout` 124. The process exits with `exit_status`.
- On `ok`: `reply` is the short text to show in the chat (in `interpreter.reply_language`, else the
  language of the owner's message); `needs_answer` is true only when `reply` is ONE question, which
  the owner answers in the same box; `items` are the items this message ADDS or CORRECTS.
- On anything else `reply` is null, `items` is `[]` and `detail` says why. The host keeps the owner's
  message and shows "I could not interpret it, it is noted": nothing is lost, the next session's
  review picks the message up as raw text.

## An item (stored by the host in the session file)

Schema 2 of the session file: `comments[]` (the thread: `role` owner/agent, `text`, `state`, `case`,
`page`, `at`) and `items[]`:

```json
{"id": "item-1", "kind": "change", "summary": "...", "node": "uc-...", "page": "/ads/new",
 "from_messages": [4], "withdrawn": false}
```

- `kind`: `change` (a defect, retouch or improvement that keeps what the product is for: launched
  directly), `decision` (changes WHAT the product does: the owner confirms it at the start of the next
  session, `dec-a-change-to-the-what-is-merged-only-on-the-owners-word`), `question_of_what` (touches
  the what with no decision stated: stays open until the owner answers).
- `id` is assigned by code (`item-N`, after the highest the request carried), never by the model. The
  host stores an item whose `id` it already holds by REPLACING it (a correction) and appends the rest.
  `withdrawn: true` means the owner no longer wants it: ingestion skips it.
- `node` is the case's id or null; `page` as the message carried it; `from_messages` are positions in
  the whole thread, the new message's included. One message with several things yields several items.

## Configuration

`interpreter:` section (`config.example.yaml`): `reply_language` (default empty: the owner's own),
`timeout_seconds` (60), `effort`, `max_thread_messages` (40). Model and per-invocation ceilings:
`classes.interpreter` (`role: interpreter`, Sonnet 5.5 by default, not Haiku: it decides which case a comment points at (docs/adr/2026-10-10-puntals-and-mechanical-tasks-default-to-haiku-5-5.md), no `fallback:`). Host paragraphs:
`project.prompt_extras.interpreter`. Logs, `runs.tsv` and `telemetry.jsonl` (the puntal's record, with
`class: interpreter` and `action: interpret_feedback`, so cost per message is a query) live in
`.cache/interpreter/` (`AGENT_CACHE_DIR` moves them). Tests put a fake `claude` first via
`INTERPRETER_CLAUDE_BIN`.
