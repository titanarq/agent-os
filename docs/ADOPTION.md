# Adopting Agentos

Two documents, one per layer. Read the ladder if you are starting a product; read the substrate
checklist for the GitHub, machine and config setup it rests on.

- **Starting a product with Agentos v2** -- the ladder below, written from the first host's real start
  (`proyecto_vector`, 05-09 October 2026), the first run of `docs/tree/uc-start-a-new-product.md` under
  `goal-improves-with-every-product`.
- **The substrate (v1)** -- [`adoption/substrate.md`](adoption/substrate.md): the 26-step checklist for
  taking `agent_os/` into a host (subtree, config, Apps, labels, machine, doctor, first run, pulling
  improvements). Rung 0 reuses it; the code and the doctor point to its step numbers.

## The ladder

| Rung | What | Document | First host: time / USD / rounds |
|------|------|----------|----------------------------------|
| 0 | Install: subtree, config, Apps and permissions, labels, venv, CI, paused epic | [start](adoption/v2-start-the-product.md) | 1 h 54 min / 0 / 1 PR |
| 1 | The owner's goals and signed evaluators | [start](adoption/v2-start-the-product.md) | 1 h 34 min / 0 / 1 PR + 1 for the 4th goal |
| 2 | The expert populates the tree | [start](adoption/v2-start-the-product.md) | ~10 min / 0.84 / 2 runs, 1 PR |
| 3 | `compile` in waves, issues per wave | [start](adoption/v2-start-the-product.md) | a night of fixes / 0 / 3 renders |
| 4 | Foundations: worker + validator by hand, one ticket at a time | [build](adoption/v2-build-the-product.md) | 5 h 25 min / 43.5 / 11 tickets, 15 rounds |
| 5 | Slots in parallel | [build](adoption/v2-build-the-product.md) | 2 then 5 slots / not separate / - |
| 6 | The test session | [build](adoption/v2-build-the-product.md) | in flight |

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

Fixed so far (agent-os pull requests): #133/#134 adoption CI, #136 expert driver and prompt, #137 order and
experiments in the slice, #138/#139 pause, review gate and trailer rules, #140 doctor probes the Apps'
permissions and install templates, #141 build tickets and explicit `touches`, #142 foundations without
inheritance. In flight: dispatch headroom and planner paging, first-class rework, quota cut, per-slot
venv, `--slot` by `--issue`. Still open, no branch yet: `open-pr` `merge_failed` without a human state;
a verification command naming a missing test; `touches` in the expert prompt; the review gate reading
checks by REST and the doctor probing that call; the worker running the host's ratchet before the pull
request; the tree doctor not checking `implementation` paths; the repeated evaluators paragraph in
every ticket; slow `status`/`collect`. Slots on demand are in flight (stage 1l, no fixed number of slots).

## Not yet exercised in the first host

The planner running unattended, the guard and its timer, the notification topic, slots on demand (made but not yet seen in a first host), question
sessions through `agent-os-sessions open`, the progress board, and a second product. No steps are written
for them until a run exists.
