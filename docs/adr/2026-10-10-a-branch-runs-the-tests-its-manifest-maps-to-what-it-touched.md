# A branch runs the tests its manifest maps to what it touched, and the whole suite when four hours have passed

- Date: 2026-10-10
- Status: accepted
- Modules (to build): `agent_os/product/test_selection/` and the `agent-os-tests` command, `templates/ci-host.yml`, `.github/workflows/ci.yml`, `prompts/worker.md`, `prompts/validator.md`
- Plan: `docs/AGENTOS_V2_PLAN.md`, Stage 2, row "Test selection and coverage" (mechanism in agent-os, CI in the host)
- Tree: `docs/tree/dec-a-full-run-every-four-hours-of-development.md`, `docs/tree/fr-what-is-consolidated-is-correct.md`, `docs/tree/dec-tests-harden-they-do-not-build.md`, `docs/tree/dec-every-pull-request-gets-a-code-quality-review.md`
- Built by: #165 (selection), #166 (clock and host CI template), #168 (agent-os's own manifest and CI, worker and validator)

## Context
The suite of this repository takes over ten minutes and CI runs it whole on every pull request; a
worker or validator that runs it locally pays the same. The owner asked (2026-10-10): "solo lanzar
los tests de la rama que se haya tocado para aligerar el CI y las pruebas que hagas en local, o sea
que alguien debe especificar las pruebas que se van a pasar en el CI, categorizarlas quizás por el
caso de uso sería lo ideal. Las pruebas globales completas deben ejecutarse cada 4 horas (mientras
se está trabajando)."

The tree already decides the what: a pull request runs the tests of its branch, integration tests
live on both sides, the pull request that finds four hours since the last full run runs the whole
suite, no development means no run, and a coupling the full run finds that the selection missed gets
its integration test (`dec-a-full-run-every-four-hours-of-development`; it applies to products and to
agent-os). Not decided, and decided here: who says which tests belong to a branch, how the selection
is computed, how the four hours are counted without a timer, and how the worker and the validator
use the same thing locally.

## Decision

### Who specifies the tests: a manifest in the repository
A declarative, versioned manifest names the tests and what they verify. Its path is
`project.test_selection.manifest` (empty by default: selection is off and nothing changes for a host
that has not adopted it). It is a file, or a folder read recursively, so that a large manifest is
split by area and stays inside the quality limits (`dec-every-pull-request-gets-a-code-quality-review`).
It holds:

- `groups`: each has an `id`, `covers` (paths of the code it verifies; a directory covers what is
  under it), `tests` (files or directories) and optionally `nodes` (tree node ids). In a product a
  group is a **use case** (`id` is the `uc-...` node), which is the categorisation the owner asked
  for; in agent-os, which verifies a mechanism and not a product, a group is a module.
- `integration`: tests that live on both sides, each with `sides` (two or more group ids) and
  `tests`. It is how "a coupling nobody declared" becomes a declared one.
- `always`: cheap guards that run on every selected plan (in agent-os, the host-literal walk, which
  reads every file git knows).
- `exempt`: paths that affect no test (changelog notes).
- `test_globs`: what counts as a test file (default `tests/**/test_*.py`).

It is written by whoever writes the ticket: the expert when it writes a use case's hardening ticket
(`docs/tree/dec-tests-harden-they-do-not-build.md`: tests come after use accepted the behaviour, so a
young product has no manifest and runs whole), the task writer in a v1 backlog. The worker that adds
a test adds its entry in the same pull request, and the validator judges the placement and any
coupling the diff shows. The owner writes none of it. Two mechanical guards:

- `agent-os-tests check` runs in CI on every pull request, whatever the plan: a test file matched by
  `test_globs` that no group, integration or `always` maps fails with a message that names the file
  and the manifest ("`tests/x/test_y.py` is mapped by no group: add it to the group of the use case
  or module it verifies"); so do a mapped path that no longer exists and an integration with an
  unknown side.
- The manifest only ever **selects**. The independent source of correctness stays where
  `fr-what-is-consolidated-is-correct` puts it (the owner's acceptance, the expert's tests, the
  validator on every pull request); a worker narrowing a manifest to dodge a test is caught by the
  next rule and by the full run.

### How a branch's selection is computed
`agent-os-tests plan --base REF` reads only git and files, so CI, the worker and the validator get
the same answer with no network:

1. Changed paths: the three-dot diff to the merge-base with the base, renames as both paths,
   deletions included. A missing `.git` or an unresolvable base is an error, never "nothing changed".
2. A changed path selects each group whose `covers` holds it or whose `tests` hold it (a changed test
   file selects its group). A changed node file under the tree root selects each group whose `nodes`
   lists the node or one of its ancestors. The `Node-Change` trailer is not an input: it already says
   why a commit touched the tree and CI already requires it; which node was touched is the changed
   file.
3. The plan is the tests of the selected groups, the integration tests with a selected group on any
   side, and `always`.
4. **Fail safe.** A changed path that no group covers and no `exempt` entry excuses makes the plan the
   whole suite, and the plan says which paths. A change to the manifest selects the groups whose
   entry was added or changed; a change to `exempt` or `always` is the whole suite, because it widens
   what no selection looks at. Narrowing a `covers` only leaves paths uncovered, which is the whole
   suite again. Shared fixtures and configuration (a `conftest`, the build file) are left unmapped on
   purpose: touching them is a full run.
5. If the tool cannot run (exit 2), the caller runs the whole suite and says why: a failure of the
   tool is never a reason to skip tests.

The granularity is the group's files; per-test-function selection is not attempted.

### The four hours, with no timer
Nothing is scheduled. When a CI run starts, it asks when the last **successful full run** finished and
runs the whole suite if that was four hours ago or more (`project.test_selection.full_run_interval_hours`,
default 4), or never, or unreadable. Because the question is only asked when a pull request or a push
to the default branch starts a run, "no development, no run" holds by construction.

- The record is a tiny artifact, `agent-os-full-run`, that a successful full run uploads with a
  one-day retention. The next run reads the newest unexpired one through the Actions API with the
  default token (`actions: read`): no ref to push, no write permission for a pull request job, no
  schedule, and it works on self-hosted runners. Expiry and a failed read both mean "due".
- A failed full run uploads nothing, so the clock keeps its old origin and the next run is full again:
  a red full run is not forgotten by the next pull request, and a green one elsewhere shows the base
  itself is fine.
- A push to the default branch runs only when the clock is due, never a selected plan (the selected
  plan already ran on the pull request, on top of the base): the last merge of a work session is
  checked within the interval instead of at the next session's first pull request.
- A full run found a failure the selection missed: the fix includes the `integration` entry (and the
  test) for the two groups, which is the tree decision made operational. Its review triggers
  stay the tree's.

### Local use: same selection, same command
`"$AGENT_OS_PYTHON" -m agent_os.product.test_selection run --base origin/main` (also
`agent-os-tests run`) computes the plan and execs `project.test_command` with the selected paths, or
alone for a full plan; CI calls the same command. The worker runs it before the commit that closes a
stage, beside the quality ratchet; the validator runs it in the worktree plus the tests the issue
names, and the whole suite only when the issue's definition of done says so. A local run never carries
the clock: CI does. A host whose manifest is empty gets its `test_command` unchanged, so nothing
breaks for hosts that have not adopted it; the wrapper behind `test_command` must accept path
arguments (the documented form already is `scripts/test.sh tests/x.py`).

## Consequences
- A pull request that touches one module or one use case runs that group, its integrations and the
  guards; a change nobody mapped, or a shared file, costs the whole suite. Early manifests are coarse
  and that cost shows; #168 measures it by replaying the last merged pull requests before trusting it.
- The mapping is maintained by the same work that adds tests, and an unmapped test is a red check in
  that pull request, so the manifest cannot drift quietly.
- Concurrent pull requests that start within the same window all see the clock due and each run the
  whole suite; accepted, because the alternative is a lock between runs.
- `templates/ci-agent-os.yml` is not changed: it runs only when the mechanism itself changes (a
  `git subtree pull`), which is when a coupling can appear, and its suite stays whole.
- A host adopts it by writing a manifest (by use case of its tree), keeping its test wrapper
  path-friendly and re-rendering its CI template after its next `git subtree pull`; each step is an
  item of `docs/ADOPTION.md` written when the host does it.
- The coverage ratchet and the mutation indicator of the same plan row are separate work.

## Alternatives rejected
- **A nightly or scheduled full run.** The owner chose a run every four hours of development, carried
  by whichever pull request is due (tree decision); a schedule also runs when nobody develops.
- **Deriving the selection from `touches` or from an import graph.** `touches` is optional and
  approximate by design (`2026-10-08-a-node-may-declare-the-code-it-touches-and-a-declaration-decides.md`),
  and an import graph is blind to what this suite mostly does: drive shell scripts and read files. A
  wrong inference is a skipped test; the manifest is explicit and reviewable.
- **Pytest markers per use case.** The mapping would be scattered across test files, an unmapped test
  would be invisible, and it would bind the design to one language.
- **A path-filtered workflow per area.** A skipped workflow reports no check, and a pull request with
  no check can never be merged
  (`2026-09-24-a-pr-with-no-checks-fails-the-ci-condition-and-every-host-ships-a-ci.md`).
- **A ref pushed by CI as the clock.** It needs write access from a pull request job and survives
  forever, so a stale one would hide that a full run is due.
