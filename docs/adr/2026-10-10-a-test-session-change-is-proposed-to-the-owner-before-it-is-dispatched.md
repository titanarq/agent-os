# A test-session change is proposed to the owner in the chat before it is dispatched

Date: 2026-10-10. Amends `2026-10-09-a-chat-test-session-is-ingested-directly-except-decisions.md` (its point 2: a `change` is
launched directly). Tree: `docs/tree/dec-a-test-session-happens-inside-the-app.md` (the owner's "Directo, salvo decisiones"; its
rejected alternative "wait for the owner's confirmation before launching any change" is reopened *for now* by the owner's order
below), `dec-a-question-session-is-a-github-issue`, `fr-the-owner-is-asked-only-in-sessions-they-open`,
`dec-a-change-to-the-what-is-merged-only-on-the-owners-word`, `dec-a-soft-product-decision-is-the-refiners-and-a-hard-one-the-owners`,
`dec-obey-while-challenging`. Issues: #167 (this design), #169, #170, #171.

## Context

The owner, 2026-10-10: *"Por ahora vamos a poner este punto de parada, para que yo valide si el trabajo que le vas a dar a cada
worker está de acuerdo con mi idea (que he podido transmitir mal)"*; *"el chat existente debe ser el canal para resolver las dudas
que agentos tenga apuntadas para mí"*; *"no creo que haga falta añadir más funcionalidad"* in the UI.

The live case is proyecto_vector#74. One comment held five items; the interpreter tied the only `change` to
`uc-ver-mis-anuncios`, the case selected in the panel, not the screen the comment was about (`/panel/anuncios/6`); `test-ingest`
opened the issue as it went, and a worker could start before the owner saw anything. The ticket then carried the owner's whole
message (#162 fixes that wording). Nothing in the pipeline shows the owner the task, the node or the context before the work
starts, and "the interpreter may misread" is the premise of the owner's own words ("que he podido transmitir mal").

What the code does today: the host sends each message to the interpreter (stateless, one turn, no tool); the interpreter answers
`reply`, `needs_answer` and the items the message adds or corrects; the host stores the thread and `items[]` in the session file,
which only the host writes; `agent-os-sessions test-ingest` (run by an operator, not on a timer) reads the file and opens one
keyed issue per non-withdrawn `change`, and writes `understood.json` for the app.

## Decision

1. **A `change` item has a state, and the state is the item's.** `status` is `proposed` or `approved`, written only by the
   interpreter's code, stored verbatim by the host in `items[]` and read by `test-ingest`. The two other facts the owner listed are
   not states of that field: *launched, with its issue number* is Agentos's and already exists as `understood.json`
   `changes[].issue` plus the idempotency key; and *corrected* is not a state, because a correction is the same item rewritten, which
   returns to `proposed`, so what is approved is always the last thing shown. (The proposal was to mark the session file too. It
   cannot be: the file is the host's and is rewritten whole by its own routes, and a second writer would lose data. Agentos writes
   only `understood.json`, as `2026-10-09-a-chat-test-session-is-ingested-directly-except-decisions.md` fixed.) `decision` and
   `question_of_what` items carry no status and are unchanged: they wait for the owner's word when a session opens.
2. **The proposal is the interpreter's reply, with `needs_answer`.** For each proposed change, in the owner's language and in
   functional words (`2026-09-15-a-question-for-the-human-is-written-in-their-language-and-in-functional-terms.md`): the task, the
   case **by its title** and the page; once for all: what each worker will be given (the owner's messages the item came from and the
   case's description, which is what #162 puts in the ticket) and what is left out (the other items of the message, each a task of
   its own, and decisions or doubts of what, which only the owner decides); then ONE question. It is a chat message and nothing
   else: no new control in the UI. While any change is `proposed`, every reply ends with the question again. Example (illustrative,
   for the message of #74):

   > *Esto es lo que encargaría: 1) Rehacer la maquetación de la página del anuncio en dos columnas, con el anuncio en un recuadro
   > visible (caso «Ver mis anuncios», página /panel/anuncios/6). Cada trabajador recibe tus palabras tal cual y la descripción del
   > caso, nada más de la conversación. Dejo fuera, porque las decides tú: editar los datos personales, imprimir solo el QR, la vista
   > previa del PDF y el sitio para responder mensajes. ¿Lo lanzo así, o corriges la tarea o el caso?*
3. **The owner's answer is read by the interpreter, and code bounds what it can do.** An explicit yes to an item approves it; a yes
   with a condition is a correction and the item is proposed again; a no is `withdrawn` (the existing mechanism); doubt is ONE
   question. `approved` is accepted only (i) with the guard on, (ii) on an item the request carried as `proposed`, (iii) of kind
   `change`, (iv) with kind, summary, node and page identical to the ones carried. An item born in the same turn is always
   `proposed`: "launch everything" written before seeing the proposal does not count. A breach is a reason for the interpreter's
   one retry, not a silent downgrade, because the reply may already say it was accepted. So what the owner approves is exactly
   what was shown, and the issue's text is that item's summary.
4. **The node is always shown and correctable in the same dialog.** The proposal names the case by title; the brief lists the
   tree's use cases (id, title) so that "no, it is about X" can move the item (a correction, back to `proposed`); and an item's
   `node` must be the case or a listed one, which closes the gap of today (an unknown id only fails at ingestion, as a `problem:`).
5. **`test-ingest` launches a `change` only when `approved`.** A `proposed` one, or one with no status, is printed as waiting and
   listed in `understood.json` under a new `proposals`. The raw-text fallbacks (rework by state, change by state, general change) are
   **held**, also listed: no interpreter read them, so there is nothing to put in front of the owner, and they are exactly the path
   by which the guard would leak. Schema 1 sessions (closed with the owner's button, no chat) are unchanged. `understood.json` stays
   schema 1, with two additive lists, `proposals` and `held`.
6. **The guard is configuration, default on "for now".** `sessions.confirm_before_dispatch` (boolean, default `true`), in a new
   `sessions:` section read by both the interpreter and `test-ingest`. Off: the interpreter proposes nothing and its changes leave
   `approved`, and `test-ingest` ignores the status, which is today's "directly". With the guard on, an item with no status (a file
   from before) counts as `proposed`: when in doubt, nothing is launched. The section is not `tree:` (where
   `test_sessions_dir` and the ticket keys live) because the guard is about the owner's session and the interpreter reads it too.
7. **Build**, in this order: #169 (key and `status` in the contract and both parsers; no behaviour), #170 (interpreter: points 1 to
   4), #171 (`test-ingest`: point 5; merged last, because with the key on by default it is what makes the guard bite). #170 and #171
   touch different files and can be written in parallel. Tests are of the pieces; none of a use case the owner has not tried.

## Work in the hosts (described here; opened in each host)

The first host's chat (`web/app/shell/sessions/thread/`) needs, **before it pulls the subtree that contains #171**:

- **Keep the status.** `reply._store` copies only `id, kind, summary, node, page, from_messages` (and `withdrawn`); add `status`, or an
  approval is lost on the way to the file and nothing is ever launched.
- **Send every item of the session** in the request, not those with `node == case`. The contract says "the items already interpreted
  in this session" (`docs/FEEDBACK_INTERPRETER.md`); the host narrows them to the case's thread, so a node correction would move the
  item out of the thread where the owner is answering and the next "ok" would find nothing. It is also why two cases both get
  `item-1` and `_store` renumbers; with all items sent that workaround stops firing.
- Optional, and not needed by this design: read `understood.json` (`proposals`, `held`, `changes`) for "lo que entendí y en qué
  quedó"; the host does not read it yet.

Until both exist the safe failure is a quiet one: with the key on nothing launches and the interpreter asks again. A host that
pulls the subtree before it has done this sets `sessions.confirm_before_dispatch: false` in its `config/agents.yaml`, in the same
pull request as the pull, to keep launching directly in the meantime (a strict config refuses the key before the pull).

## Rejected alternatives

- *Record the state in the session file from Agentos.* See 1: single writer, whole-file rewrite.
- *The proposal rendered by code from the ticket.* "What is shown is what is done" is attractive, and 3 gets it differently
  (approval binds the exact item). But the ticket is the worker's document, in the repository's language and seven sections; the
  owner would read engineering text in a foreign language, and a code template has no way to speak theirs. The model writes the
  words, code checks the facts (case title, page, `needs_answer`).
- *A question-session issue per proposal* (`dec-a-question-session-is-a-github-issue`). That issue freezes questions recorded on
  nodes, with a default answer; a proposal has neither, and it would send the owner out of the session they have open, against
  `fr-the-owner-is-asked-only-in-sessions-they-open`, for a question the chat answers in seconds.
- *Buttons "launch" and "edit" in the panel.* The owner asked for no more UI; the chat already carries a question and its answer.
- *Silently downgrading a bad `approved`.* See 3.
- *Default off.* The owner asked for the stop now; the key is how it is removed later.

## Consequences

The guard reopens, by configuration and by the owner's order, what `dec-a-test-session-happens-inside-the-app` rejected
(confirm before launching any change); with the key off the tree's "Directo, salvo decisiones" is exactly what happens. The tree
needs one owner-approved line in that decision recording that the alternative is reopened for now and by which word; this ADR
does not touch `docs/tree/` (`dec-obey-while-challenging`: the decision binds until the owner changes it, and the owner has).
A `decision` still waits for the owner and the refiner/owner split by hardness is untouched
(`dec-a-soft-product-decision-is-the-refiners-and-a-hard-one-the-owners`). Cost: one more turn per comment that holds a change.
Launching after the "ok" still waits for whoever runs `test-ingest` (an operator step today); a host call that opens only the
approved issues would be a later change and is not decided here.

## Review triggers

The owner approves a long run of proposals with no correction (for example twenty): offer to turn the key off. The owner corrects
the node in many proposals: the choice of case versus page needs fixing at its source, not by asking every time. A worker's
validator rejects a ticket as "not what the owner described" after an approval: the proposal omitted something. A held fallback
waits longer than a session: it needs a way out (the interpreter re-reading the message). The owner stops answering proposals and
changes pile up as `proposed`.
