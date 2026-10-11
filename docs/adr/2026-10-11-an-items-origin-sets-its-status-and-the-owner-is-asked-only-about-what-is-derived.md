# An item's origin sets its status, and the owner is asked only about what the interpreter derives

Date: 2026-10-11. Amends `2026-10-10-a-test-session-change-is-proposed-to-the-owner-before-it-is-dispatched.md` (#167: the guard is
no longer on by default and no longer the only reason an item waits) and `2026-10-10-a-verdict-a-correction-and-an-open-question-go-through-the-chat.md`
(#178, point 3: "a `puntal_change` is always proposed" goes). Tree: `docs/tree/dec-a-test-session-happens-inside-the-app.md`,
`dec-a-change-to-the-what-is-merged-only-on-the-owners-word`, `fr-the-owner-is-asked-only-in-sessions-they-open`,
`dec-obey-while-challenging`, `dec-tests-harden-they-do-not-build`. Issue: #203.

## Context

The owner, 2026-10-11: *"si la corrección la planteo yo no, si la derivas de algo que te he dicho, me la preguntas en el chat sobre la
marcha. [...] algo que detectes que haya que corregir, entonces lo ideal es que lo apliques directamente y me lo comentes como
pregunta, pero con la pre-aceptación por mi parte, pues esas correcciones deben ser casos que no son compatibles con criterios que
están por encima de los del caso de uso corregido, como: los objetivos"*, and *"todo es interpretado, para eso tenemos un chat [...] y
si tiene dudas, repreguntar"*. The guard of #167 was for one review: *"hasta que no vuelva a solicitar otra revisión de todo, no es
necesario esperar confirmación antes de lanzar nada"*.

## Decision

1. **Every item carries an `origin`**, written by the interpreter: `stated` (the owner said it as it is), `derived` (the interpreter
   deduces it from what the owner said) or `detected` (Agentos noticed it because it clashes with a criterion above the case: a goal
   or an evaluator of the tree). The brief now lists the goal and requirement above the case so that `detected` has something to
   clash with.
2. **Code sets the `status` from the origin**, for `change`, `decision`, `puntal_change` and `verdict`: `stated` and `detected` are
   born `approved`, `derived` is born `proposed`. A `proposed` item is asked about in the chat and only it waits; the rest goes on.
   A `detected` item is applied and the reply comments it as a question already accepted; if the owner says no, the interpreter
   withdraws it and proposes (a `derived` item) the change that reverts it. `approved` stays bound to what the owner was shown.
3. **Review mode is the key**, `sessions.confirm_before_dispatch`, now **default false**: the owner turns it on when they ask for a
   review of everything, and then every new or corrected item is born `proposed`, as in #167. `test-ingest` follows the same
   line: with it off only an item marked `proposed` waits (a status-less item of a file from before is launched); with it on only
   `approved` is launched and the raw-text fallbacks are held.
4. **A `puntal_change` is no longer special**: it follows its origin like any item. Its issue still opens only on
   `sessions.mechanism_repository`, and with that empty it is held.
5. **A decision's status records whose word it is, nothing more.** `test-ingest` still keeps every decision for the owner to confirm
   when the next session opens, so `dec-a-change-to-the-what-is-merged-only-on-the-owners-word` holds; applying an approved
   decision to the tree is the consolidation of the use cases, out of scope here.

## Consequences

The code cannot check that a `detected` item really clashes with a criterion: the guard is the prompt (it names the criterion in the
summary, and when in doubt the item is `derived`) and the owner's "no", which reverts. A host that set the key explicitly keeps its
value; one that relied on the old default now launches stated and detected items without waiting.
