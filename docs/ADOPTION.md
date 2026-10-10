# Adopting Agentos

Three documents in two layers. Read the ladder (two files) if you are starting a product; read the
substrate checklist for the GitHub, machine and config setup it rests on.

- **Starting a product with Agentos v2** -- the ladder below, written from the first host's real start
  (`proyecto_vector`, 05-09 October 2026), the first run of `docs/tree/uc-start-a-new-product.md` under
  `goal-improves-with-every-product`.
- **The substrate (v1)** -- [`adoption/substrate.md`](adoption/substrate.md): the 26-step checklist for
  taking `agent_os/` into a host (subtree, config, Apps, labels, machine, doctor, first run, pulling
  improvements). Rung 0 reuses it; the code and the doctor point to its step numbers.

## The ladder

| Rung | What | Document |
|------|------|----------|
| 0 | Install: subtree, config, Apps and permissions, labels, venv, CI, paused epic | [start](adoption/v2-start-the-product.md) |
| 1 | The owner's goals and signed evaluators | [start](adoption/v2-start-the-product.md) |
| 2 | The expert populates the tree | [start](adoption/v2-start-the-product.md) |
| 3 | `compile` in waves, issues per wave | [start](adoption/v2-start-the-product.md) |
| 4 | Foundations: worker + validator by hand, one ticket at a time | [build](adoption/v2-build-the-product.md) |
| 5 | Slots in parallel | [build](adoption/v2-build-the-product.md) |
| 6 | The test session | [build](adoption/v2-build-the-product.md) |

The time, USD and rounds the first host measured for each rung are in that rung's **Baseline**.
Elapsed from the owner's first goal (07-10 20:01) to the first real puntal answering a click on the real
shell (09-10 about 16:35): about 44 h, most of it spent fixing the mechanism, not building the product.

## How to read a rung

Each rung says what it is, why (the tree node that backs it), how (generic commands, in order), how it is
checked, what failed the first time and whether that is fixed in code or the doctor or is still an open
edge, and the baseline the first host measured. What only the first host did is marked **First host**.
Placeholders: `<N>` an issue, `<PR>` a pull request, `<S>` a slot, `<node>` a tree node id.

Rules that hold on every rung: never arm the guard or its timer from a procedure (the owner does);
move issue states only with `python -m agent_os.issues move`; never edit `agent_os/` in a host
(`dec-v2-wraps-v1`); a change to the owner's what merges only on the owner's word
(`dec-a-change-to-the-what-is-merged-only-on-the-owners-word`); every pull request gets a code-quality
review (`dec-every-pull-request-gets-a-code-quality-review`).

## Measuring

Time is wall clock on the host's machine; USD is the sum of `.cache/*/runs.tsv` for workers, validators,
the expert and puntales, not the control thread. A rung's second product should be compared on the same
two measures. Numbers from one run are not a distribution: say so when you quote them.

## Open edges (each rises to code or a doctor check, and the rung text then shrinks)

What is already fixed is in `docs/CHANGELOG.md` and `git log`; only what a reader can still trip over is
listed here.

- A verification command that names a missing test leaves the worker without instruction.
- The review gate reads a pull request's checks through GraphQL (`statusCheckRollup`), not REST, and the
  doctor probes the permissions over REST, not that call.
- The evaluators paragraph repeats in every ticket.
- `status` and `collect` sometimes take over 100 s.

## Not yet exercised in the first host

The planner running unattended, the guard and its timer (armed only by the owner; the doctor stays red on
the notification topic and the timer on purpose), the notification topic, slots on demand (made, never seen
in a first host), question sessions through `agent-os-sessions open`, an open test session ingested as it
goes (run by hand over an example; the owner has not used it), the progress board
(`agent-os-tree board sync`, `docs/AGENT_OS.md`), and a second product (the baseline that
`goal-improves-with-every-product` compares against). No steps are written for them until a run exists.
