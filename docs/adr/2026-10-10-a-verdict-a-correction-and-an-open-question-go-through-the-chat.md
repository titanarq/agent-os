# A verdict, a correction and an open question of a case go through the test-session chat

Date: 2026-10-10. Amends `2026-10-10-a-test-session-change-is-proposed-to-the-owner-before-it-is-dispatched.md` (PR #175: it
adds item kinds and a second target to its proposal, and keeps its approval rules). Tree: `docs/tree/dec-a-test-session-happens-inside-the-app.md`,
`dec-a-method-change-is-judged-by-evidence-from-the-products`, `dec-a-puntal-plans-in-one-turn-and-code-executes`,
`dec-a-change-to-the-what-is-merged-only-on-the-owners-word`, `fr-the-owner-is-asked-only-in-sessions-they-open`,
`dec-a-doubt-of-how-is-settled-by-an-experiment`. Issues: #178 (this design), #179, #180, #181, #182, #183.

## Context

The owner, 2026-10-10: *"Si el puntal no responde de forma adecuada lo voy a decir en el chat igual que el resto de cosas que vea
mal, por eso ese chat tiene que leerlo alguien con el poder suficiente para modificar las instrucciones del puntal o cambiar el
caso de uso"*; *"El chat, como digo, es el único canal para hacerme preguntas y para que te dé feedback"*; and, of the test UI,
*"no creo que haga falta añadir más funcionalidad"*.

Two things still go through boxes of the host. (a) The verdict on ONE improvised answer (accept, reject, retry), recorded in
`feedback.jsonl` against the puntal's `invocation_id`, is given on the final pages (the host removes those boxes in
proyecto_vector#75); a signed evaluator of the host's `goal-web-operable` requires it ("every action answers ... its verdict is
recorded against that invocation") and so does "what was accepted keeps holding". Evaluators are not rewritten: the same
requirement is served through the chat, with the same record. (b) The open questions of what of a case (each with its default
answer) are answered in a box of the side panel, which writes `questions[].answer` in the session file.

The interpreter (`agent_os/product/interpreter/`) is one stateless turn with no tool; the host stores `items[]`; `test-ingest` reads
them. The ADR of #175 gives a `change` the status `proposed`/`approved` and has the interpreter propose it in the chat.

## Decision

1. **The chat knows which answer the owner means because the host tells it.** The request gains `invocations`: the last
   `interpreter.max_invocations` (default 5) invocations of the puntal on the page and the case the message carries, each
   `{invocation_id, action, node, page, at, answer}` (the answer cut to a fixed length). The host has them (its own envelopes and
   the puntal's telemetry). The model never invents an id: an item that points at an invocation names one the request carried, or
   it is a reason for the interpreter's one retry, as an unbound `approved` is. The reply names the answer in functional words
   ("la respuesta a «Reenviar anuncio» de las 10:32"); the most recent one on that page is the default, and when two fit equally
   the interpreter asks ONE question. An item keeps `invocations: [ids]`, so the comment stays tied to them.
2. **"This answer is wrong" yields one of three items, and the owner chooses.**
   - `verdict`: `accept`, `reject` or `retry` on ONE invocation, with the owner's note. It launches nothing. `retry` records the
     verdict only; the owner repeats the click if they want another answer.
   - A correction aimed at the **use case** (the node of the host). The node's description is the puntal's instruction. A change
     of *how* it answers is a `change` (the ADR of #175: proposed, approved, issue). A change of *what* it should do is a `decision`
     and waits for the owner at the next session, as today: `dec-a-change-to-the-what-is-merged-only-on-the-owners-word`.
   - A correction aimed at the **puntal's instructions** in agent-os (`prompts/puntal.md`, the node-slice rules): a new kind,
     `puntal_change`. It does not change a prompt; it opens one issue on agent-os, with a TASK and a CONTEXT separated, whose task
     is to assess the behaviour, reproduce it as a case of the replay battery and change the prompt only if the battery says so
     (`dec-a-method-change-is-judged-by-evidence-from-the-products`: never a blind change, and nobody grades its own method). The
     CONTEXT carries the owner's words, the action, node, answer and `versions` of the invocation, and the case's description.
   Any of them may carry the invocation as evidence. **Who decides the target:** the interpreter proposes it with its reason, in
   functional words ("tu caso dice X y la respuesta lo cumple: cambiaría el caso" or "tu caso dice X y la respuesta no lo
   cumple: pediría revisar las instrucciones del puntal"), and the owner confirms or corrects it in the same dialog, as they do
   with the node (#175, point 4). Its rule of thumb is in the prompt: the answer follows a description that is wrong or silent,
   the case; the answer ignores a clear description, the puntal. When it cannot tell, ONE question. At most one target per item.
3. **The power of whoever reads the chat is to propose, never to merge.** The reader is the interpreter and the code around it;
   what they can do is put a verdict, a correction of the case or a correction of the puntal in front of the owner and, on their
   yes, open the issue. Nothing is merged by the chat. A change to what a case is for stays a `decision`; a pull request that touches
   a goal or an evaluator stays merged only on the owner's word. Both of the ADR of #175 stand: `approved` is code-bound to the
   item shown, and `sessions.confirm_before_dispatch` governs `change`, `verdict` (born `approved` when it is off). **A
   `puntal_change` is always proposed**, whatever that key says: it is the one item that reaches Agentos's own method, which the
   key's "for now" never meant to loosen.
4. **Open questions of what come to the chat as an agent message, one at a time.** The host, when the owner selects a case with an
   unanswered `what` question (and no proposal waits), calls the interpreter with `ask: {node, question, default_answer}` and no
   message. The interpreter writes ONE message in the owner's language with the question and its default in words ("si no
   contestas, vale: ..."), `needs_answer` true, no items; the host stores it with the `ask` it came from. The next message
   carries it as `pending_question`. If the message answers it, the interpreter emits an `answer` item whose `answer_text` is set
   by code to the owner's message verbatim (an explicit yes to the default sets the default's text), bound to the carried question
   (node and text identical); its reply says what it wrote down. The host stores `answer_text` in `questions[].answer` through the
   same function behind its `test_sessions.answer` endpoint; the file's shape and `test-ingest`'s transcription (the owner's words,
   exactly, into the node) do not change, so the panel box can go without losing anything. An `answer` needs no approval: it is the
   owner's word, as in a question session. Not answering leaves the default standing, which the message already said.
5. **Several items in one reply are ordered and closed by ONE question.** In this order: what is recorded without launching (the
   `answer`), then the numbered proposals (verdicts, case corrections, puntal corrections, changes), then what is left out
   (decisions and doubts of what, which the owner decides), then ONE "¿de acuerdo?". The owner answers it for all or by number; a
   yes with a condition rewrites that item, which returns to `proposed`. While any proposal waits, no open question is asked.
6. **Verdicts are recorded by `test-ingest`, not by the host.** The session file stays the host's and `feedback.jsonl` is the
   puntal's record; `test-ingest` already reads the latter and runs where it lives. An `approved`, not withdrawn `verdict` is
   appended to `feedback.jsonl` as `puntal_task.sh feedback` would (`versions`, `action`, `node` copied from the invocation's
   telemetry; an unknown invocation is a `problem:` line), keyed by `chat-verdict.<session>.<item>`, so a second run adds
   nothing. Same record, same file, same keys as the boxes: the evaluators read what they read. The cost is the delay until the
   operator runs `test-ingest`; nothing here makes that faster.
7. **`puntal_change` needs a repository.** `sessions.mechanism_repository` (owner/name, default empty). Empty: the item is
   **held** and listed in `understood.json`, nothing opened. A host-specific value is a config key, never a literal.
8. **Build**, in this order, after #169, #170 and #171: #179 (contract: kinds, request fields, two keys; no behaviour), #180
   (interpreter: points 1 to 3), then #181 (interpreter: points 4 and 5; same prompt, so after #180), and, once #179 and #171 are
   in, #182 (`test-ingest` records verdicts) then #183 (`test-ingest` opens the `puntal_change` issue; both edit the plan and
   apply of the chat ingestion, so in series). #180 and #182 are parallel. Each is under 80K tokens of work; tests are of the
   pieces, none of a use case the owner has not tried.

## Work in the hosts (described here; opened in each host)

For the first host (`web/app/shell/sessions/thread/`), after it pulls the subtree that has #179 to #181:

- **Pass `invocations`** in each request: the last invocations of the puntal on the message's page and case, with the answer
  each gave. The panel needs no new control.
- **Store the new fields.** `reply._store` copies a fixed list of keys (the same one #175 asks to extend with `status`): add
  `invocations`, `verdict`, `note`, `answer_text`.
- **Ask the open questions**: on selecting a case with an unanswered `what` question, and when no proposal waits, call the
  interpreter with `ask` and store the agent message with its `ask`; on the next message, send it as `pending_question`.
- **Write the answer**: on an `answer` item, call the function behind `test_sessions.answer` with `answer_text`. Then remove the
  box of the side panel (`shell/sessions/_detalles.html`, "Guardar la respuesta"); the endpoint can stay for the code path.
- The verdict boxes of the final pages go in proyecto_vector#75; they leave before the chat covers them only if the owner
  accepts a gap, otherwise after the host has done the first and second points.

## Rejected alternatives

- *A control per answer in the page ("this is wrong").* The owner asked for no more UI and named the chat the only channel.
- *The model names the invocation by free text.* Code cannot check it; the carried ids can be.
- *The chat edits the case's description or the prompt itself.* A prompt changes on evidence, a case's what on the owner's word;
  the chat proposes and the issue carries the work.
- *The host records the verdicts.* It would be a second writer of the puntal's feedback file and a thing to forget; the ingestion
  already holds the keys that make it idempotent.
- *The interpreter writes the open question from the tree's text without a model turn.* The tree's text is in the repository's
  language; the owner reads Spanish (`2026-09-15-a-question-for-the-human-is-written-in-their-language-and-in-functional-terms.md`).
- *The answer to an open question confirmed before it is written.* It is the owner's own answer to a question with a default; one
  extra turn buys nothing, and the reply already says what was written.
- *`puntal_change` under the `confirm_before_dispatch` key.* See 3.

## Consequences

A puntal that answers badly is judged in the place the owner already writes, with the invocation attached, and the verdict reaches
the same file the evaluators read. The method of the puntal only moves on battery evidence, however sure the owner is: a
`puntal_change` that the battery does not support closes without a change, and the issue says why. Cost: one more field set in
the host's request and store, a model turn per asked question, and the lag of the ingestion for verdicts.

## Review triggers

The owner corrects the target (case versus puntal) in many proposals: the rule of thumb in the prompt is wrong. The owner gives
a verdict by hand again after the chat took it over: the chat's invocation guess is poor. Verdicts wait for an operator longer
than the owner's patience: a timer or a host call that runs `test-ingest`. The `puntal_change` issues are mostly closed with no
change: the owner is misreading the cause or the battery is too weak.
