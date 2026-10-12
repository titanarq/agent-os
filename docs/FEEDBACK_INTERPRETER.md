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
| `message` | required, except on an `ask` request, which carries none (one is refused). The owner's new message: `text` (non-empty), `state`, `case`, `page`, `at` (all optional, free text; `state` is the host's own verdict word, e.g. `perfect`, `ok_with_improvements`, `needs_improvement`, `incorrect`). |
| `thread` | the stored messages so far, in order, each `{role: owner\|agent, text, state, case, page, at}`. Pass ALL of them in stored order: positions in `from_messages` are positions in this list, and the new message is at position `len(thread)`. |
| `case` | optional `{id, title, description, verification: [text, ...]}`. When absent and `message.case` is set, the node is read from the host's product tree (`--tree-root`, default `tree.root`); a case the tree does not have is a refusal. |
| `page_node` | optional `{id, title, description}` (or only the id, read from the tree): the node of the page the owner is commenting on, which may differ from `case`. The brief carries it and the prompt tells the model to pick the item's `node` from it first. A node it names is accepted as an item's `node` in proposal mode. The host sends it (a host change, not part of Agentos). |
| `items` | the items already interpreted in this session (the shape below), so the model corrects instead of duplicating. |
| `invocations` | optional. The most recent `interpreter.max_invocations` invocations of the puntal on the message's page and case, each `{invocation_id, action, node, page, at, answer}` (`invocation_id`, `action` required; `answer` text cut by the host; an id twice is refused). An item that points at an answer names one of these ids. |
| `pending_question` / `ask` | optional, never both. `{node, question, default_answer}`, all non-empty text: the open question of what the owner may be answering (`pending_question`), or the one the interpreter is to put (`ask`). With `ask` the reply is ONE agent message (the question and its default in words), `needs_answer` true, no items; an `ask` while an item is `proposed` is a refusal (no open question is asked while a proposal waits). With `pending_question`, a message that answers it yields ONE `answer` item whose `node`, `question` and `answer_text` are set by code: the owner's message verbatim, or the default's text when the model marks an explicit yes to it. Several items in one reply go in this order, closed by ONE question: the `answer`, the numbered proposals, what is left out. A malformed one, or a malformed `invocations`, is `not_run`. |
| `session_id`, `invocation_id`, `labels` | recorded in the telemetry. `invocation_id` defaults to a UUID. |

## The envelope (stdout)

`schema` (1), `invocation_id`, `outcome`, `exit_status`, `detail`, `message_position`, `reply`,
`needs_answer`, `items`, `retries`, `cost_usd`, `usage`, `latency_s`.

- `usage` and `latency_s` are what the host copies into its own line of the puntal telemetry file
  (`tokens` / `usage`, `latency_s.total`) so the cost of a message is a query there too: `usage` is the
  `usage` of the interpreter's own telemetry record (`input_tokens`, `output_tokens`, the cache counters,
  `total_tokens`, the first-turn figures), summed over the retry when there was one; `latency_s` is
  `{"total": seconds}` from the moment the process was entered to the moment it had its answer. Both are
  `null` on `not_run` (nothing ran); on a failed run they hold whatever the turns had streamed.

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
{"id": "item-1", "kind": "change", "origin": "stated", "status": "approved", "summary": "...",
 "node": "uc-...", "page": "/ads/new", "from_messages": [4], "withdrawn": false}
```

- `kind`: `change` (a defect, retouch or improvement that keeps what the product is for: launched
  once approved), `decision` (changes WHAT the product does: the owner confirms it at the start of the next
  session, `dec-a-change-to-the-what-is-merged-only-on-the-owners-word`), `question_of_what` (touches
  the what with no decision stated: stays open until the owner answers).
- Three more kinds (`docs/adr/2026-10-10-a-verdict-a-correction-and-an-open-question-go-through-the-chat.md`; the
  the interpreter reads `invocations` and proposes `verdict` and `puntal_change`, `answer` comes after): `verdict` (`invocations`: exactly one id, `verdict`: `accept`, `reject` or
  `retry`, optional `note`), `puntal_change` (a correction of the puntal's instructions: `summary`, `invocations`, `node`,
  `page`) and `answer` (`node`, `question`, `answer_text`, all required). Any item may carry `invocations: [ids]`; each of
  these fields is omitted from the item's JSON when empty. The interpreter's parser and the session reader accept them.
- The brief lists the carried `invocations` (the answer cut to 600 characters). The prompt teaches the three outcomes of "this
  answer is wrong": a `verdict` on ONE invocation; a `change` or `decision` on the case (its description is the puntal's
  instruction) with the invocation as evidence; a `puntal_change` (the puntal ignored a clear description). The interpreter
  proposes the target with its reason and the owner confirms or corrects it in the dialog; an ambiguous answer or target is ONE
  question. Code binds it: an item that names an id the request did not carry (an item the session already holds keeps its own
  ids), or a `puntal_change` with no id, is a reason for the one retry. `verdict` and `puntal_change` follow the `approved`
  rules of `change` (bound to the content shown) and count as proposals in the reply; with `sessions.confirm_before_dispatch`
  off a new `verdict` is born `approved`, but a `puntal_change` is always born `proposed`.
- `id` is assigned by code (`item-N`, after the highest the request carried), never by the model. The
  host stores an item whose `id` it already holds by REPLACING it (a correction) and appends the rest.
  `withdrawn: true` means the owner no longer wants it: ingestion skips it.
- `origin` is written by the interpreter on every item (`docs/adr/2026-10-11-an-items-origin-sets-its-status-and-the-owner-is-asked-only-about-what-is-derived.md`):
  `stated` (the owner said it as it is), `derived` (deduced from what they said) or `detected` (Agentos
  noticed it because it clashes with a criterion above the case: a goal or an evaluator; the brief lists
  the goal and requirement above the case). It is required on a new or corrected item and optional on
  a withdrawn one; a stored item from before may have none.
- `effect` is optional and only read on a `decision` about a use case: `adds`, `contradicts` or
  `qualifies` what the case already says (`docs/adr/2026-10-12-a-use-case-that-an-amendment-contradicts-is-consolidated-into-one-definition.md`).
  Ingestion opens ONE consolidation issue (key `consolidate.<node>`, reused while open) when a decision
  contradicts or qualifies and no decision on that case is still `proposed`; `adds`, or none, raises nothing. The issue carries `project.labels.consolidation`, never a worker's label;
  `agent-os-consolidate <issue>` drafts (Sonnet) and reviews (Opus) it into one pull request.
- `status` is optional: `proposed` (the item was put to the owner) or `approved` (the owner agreed, or
  the origin made it so); absent means the owner was never asked. Any other value is refused (the
  request, and the session reader naming the file). Only the interpreter's code writes it; the host
  stores it verbatim in `items[]`. For `change`, `decision`, `puntal_change` and `verdict` code sets it
  from the origin: `stated` and `detected` are born `approved`, `derived` is born `proposed`. The
  interpreter asks about a `proposed` item in the chat (only that item waits) and comments a `detected`
  one as a question already accepted (`needs_answer` false); if the owner says no it withdraws it and
  proposes, as a `derived` item, the change that reverts it. `question_of_what` and `answer` carry no
  status.
- With `sessions.confirm_before_dispatch` true (review mode, which the owner switches on when they ask
  for a review of everything; default false, `docs/adr/2026-10-10-a-test-session-change-is-proposed-to-the-owner-before-it-is-dispatched.md`)
  every new or corrected item is born `proposed` whatever its origin. Code, not the prompt, binds the
  answer in both modes: `approved` is kept only on an item the request carried as `proposed` (or with no
  status), of a status-bearing kind, repeated with the same kind, summary, node, page, verdict and
  invocations, and any other `approved` is a reason for the one retry (a re-sent item that was already
  `approved` and is unchanged stays so). `withdrawn` keeps its meaning. While any such item stands
  `proposed` the reply must have `needs_answer` true, ask a question, and name each proposed item's case
  (title or id) and page; a `detected` item of this turn is named the same way (its `needs_answer` stays
  false). The limit grows by `PROPOSAL_REPLY_CHARS_PER_ITEM` (400) per proposed or detected item over
  `MAX_REPLY_CHARS` (1200). With a readable tree (`--tree-root`; required in review mode, else the run
  is refused) the brief lists the tree's use cases (the case first, at most `MAX_LISTED_USE_CASES`) and
  an item's `node` must be the case or one of them, else a retry reason.
- `node` is the commented page's node when the request carries `page_node` and the item is about that page, else the case's id; null for a new capability no node covers yet (a valid item); `page` as the message carried it; `from_messages` are positions in
  the whole thread, the new message's included. One message with several things yields several items.

## Configuration

`sessions.confirm_before_dispatch` (default false) switches the review mode above. `interpreter:` section (`config.example.yaml`): `reply_language` (default empty: the owner's own),
`timeout_seconds` (60), `effort`, `max_thread_messages` (40), `max_invocations` (5). `sessions.mechanism_repository` (`owner/name`, default empty) is where a `puntal_change` opens its issue. Model and per-invocation ceilings:
`classes.interpreter` (`role: interpreter`, Sonnet 5.5 by default, not Haiku: it decides which case a comment points at (docs/adr/2026-10-10-puntals-and-mechanical-tasks-default-to-haiku-5-5.md), no `fallback:`). Host paragraphs:
`project.prompt_extras.interpreter`. Logs, `runs.tsv` and `telemetry.jsonl` (the puntal's record, with
`class: interpreter` and `action: interpret_feedback`, so cost per message is a query) live in
`.cache/interpreter/` (`AGENT_CACHE_DIR` moves them). Tests put a fake `claude` first via
`INTERPRETER_CLAUDE_BIN`.
