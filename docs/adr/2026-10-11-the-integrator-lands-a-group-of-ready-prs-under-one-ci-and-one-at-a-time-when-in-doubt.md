# The integrator lands a group of ready pull requests under one CI, and one at a time when in doubt

- Date: 2026-10-11
- Status: accepted
- Modules (to build): `agent_os/product/integrator/` and the `agent-os-integrate` command,
  `bin/dev/safe_merge.sh` (a `--group` mode), `prompts/integrator.md`, `agents/control-plane.md`
  (Duty 4), `config.example.yaml`
- Issue: agent-os#204 (this ADR). Built by #205 (integration branches are invisible to every reader
  of open pull requests), #206 (config), #207 (candidates and groups, dry run), #208 (build),
  #209 (CI result and failure attribution), #210 (landing), #211 (the judge), #212 (rounds ledger),
  #213 (the merge seat), #214 (experiment on the judge's model), #215 (a tree node)
- Tree: `docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`,
  `docs/tree/fr-independent-work-runs-in-parallel.md`,
  `docs/tree/dec-a-full-run-every-four-hours-of-development.md`,
  `docs/tree/dec-tests-harden-they-do-not-build.md`,
  `docs/tree/dec-every-pull-request-gets-a-code-quality-review.md`,
  `docs/tree/dec-a-doubt-of-how-is-settled-by-an-experiment.md`,
  `docs/tree/dec-a-method-change-is-judged-by-evidence-from-the-products.md`,
  `docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`; and, on the open pull
  request #153 (not yet in `main`, cited by id), `goal-efficient-with-what-it-spends` and
  `fr-merge-work-is-not-reviewed-twice`
- Supplements, does not amend: `2026-09-17-the-control-plane-merges-a-pr-in-the-humans-name-under-five-conditions.md`,
  `2026-10-11-a-green-pr-holding-main-is-the-merge-check-and-the-full-suite-runs-on-a-clock.md`,
  `2026-10-10-a-branch-runs-the-tests-its-manifest-maps-to-what-it-touched.md`

## Context
The owner, 2026-10-11: "Agrupa PRs similares, para ello tendrás que tener a un agente que se encargue
de ver qué commits merece la pena integrar y cuales no, esto es para agilizar, por tanto ante la duda,
integrar de uno en uno"; asked whether it is for Agentos: "Sí, para Agentos".

Measured on 2026-10-11. The verification of a merge is the pull request's own green run on a head that
contains `origin/main` (`bin/dev/safe_merge.sh` refuses anything else; the push trigger on `main` is
gone). So every merge makes every other ready pull request stale: it needs a refresh and a new CI of
about 9-13 minutes here and 5-25 in a host before it may merge, and the next merge makes it stale
again. A host runs up to five workers at once, so up to five pull requests can be ready together, and
by arithmetic on the measured range they merge one CI after another: about five CIs of waiting for the
last one, on the same machine that runs the next workers. Most of those pull requests have nothing to
do with each other.

What exists and is reused: the start gate keeps two tickets that share code from running at once
(`dec-dispatch-never-runs-two-tickets-on-the-same-code`), so ready pull requests are mostly disjoint;
`agent-os-tests plan` computes the tests of any diff from a manifest; `wait_checks.sh` reads CI as
one line; the control plane merges in the human's name under six conditions, and the mechanism's own
roles never merge (`2026-09-17-the-control-plane-merges-a-pr-in-the-humans-name-under-five-conditions.md`).

## Decision

### What the integrator is
An **accelerator in front of the merge, never a new merger**. It takes pull requests that the merge
seat has already approved, proves a group of them together with one CI, and lands them. Whatever it
declines to group goes through the flow that exists today, unchanged, so the integrator can only make
a merge faster, never make one that today's flow would refuse. It is script-first: everything
mechanical is code, and one LLM turn exists only for the judgment of "independent or not".

The six merge conditions (`docs/AGENT_OS.md` §2.4) still hold for each pull request and are still
verified by whoever merges, before the integrator is called; condition 1 reads "green on the head's own
CI", and the integration CI is an addition. The integrator receives an approval and never grants one,
so the decision of 2026-09-17 stands: a pull request that touches the owner's what
(`guard-what`, `dec-a-change-to-the-what-is-merged-only-on-the-owners-word`) is never handed to it.

### Who launches it, and when
The seat that merges: the human or the control plane in the human's name, with one command,
`agent-os-integrate`, from Duty 4 (#213). Not the planner, the guard, the validator or a worker: they
never merge, and a merge is the last step of the integration. There is no standing process, no timer
and no waiting window: it is called when two or more pull requests are approved and ready, and takes
what is ready at that moment. One integration is in flight per repository (a `flock` on
`.cache/integrator.lock`); pull requests that become ready meanwhile form the next group, so they wait
at most one CI, no more than today. With one ready pull request, or `integrator.enabled: false`, the
merge seat acts exactly as before.

### How it chooses a group
1. **Candidates (script).** Open, not a draft, targeting the default branch, mergeable, every check
   SUCCESS on its current head, approved by the validator or by the merge seat on that head, and not in
   rework. Any fact the script cannot read makes that pull request solo.
2. **Allowed groups (script).** Greedy, oldest pull request first, one group per round. A group may
   hold pull requests that have: the same base; changed paths pairwise disjoint (renames count as both
   paths, through `agent_os.product.test_selection.changed_paths`) and, in a v2 host, disjoint node
   `touches` (the data the start gate reads); no path under `integrator.solo_paths`; an own test plan
   that is not the whole suite; and at most `integrator.max_group_size` members.
3. **Judgment (LLM, once per round).** What disjoint paths cannot show is a coupling in meaning: a
   changed contract that another pull request's files call, one setting changed from two files, one
   claim edited in two documents. The judge reads an index, not diffs: per pull request its number,
   title, the title of the issue it closes, its files, the test groups its plan selects, the hunk
   headers of its changed symbols (at most 40 lines) and the script's numbers (tests of the union against
   the tests of the largest member, which is what makes pull requests "similar" in the cheap sense: a
   group whose union is hardly larger than its largest member is a bargain, one that doubles it is not).
   It answers `independent`, `unsure` or `coupled` with one line of reason per proposed group, and it
   may only **confirm, split or send solo** -- never form a group the script did not allow. Its output
   must partition the input; an object that does not, an unparsable one, a timeout or an exhausted
   quota all mean every pull request solo. So the LLM can never cost a wrong merge, only speed.

### When it does not group
Whenever there is doubt ("ante la duda, integrar de uno en uno"), and in particular:
- the judge says `unsure` or `coupled`, or cannot answer (above);
- the paths overlap, or two pull requests would add to the same folder past the code-quality limit
  (the build's pre-flight sees it, below);
- a pull request touches CI workflows, dependency manifests, lockfiles, the bootstrap, or any
  `integrator.solo_paths` glob a host adds: what changes the environment every test runs in is proved
  alone;
- a pull request's own plan is the whole suite (it would turn the group's CI into the longest one,
  and it already carries the clock of `dec-a-full-run-every-four-hours-of-development`);
- merging the heads produces a **conflict**. The integrator never resolves one and never edits a pull
  request's code: a conflict goes back to the rework path of the pull request's own author, which
  already holds the context of the change (`fr-merge-work-is-not-reviewed-twice`);
- the owner's what is touched, a check is not SUCCESS, or the head moved since the plan.

### How it integrates
1. Take the lock, fetch, record `base = origin/main`.
2. In a throwaway worktree at `base`, merge each member's *pinned head* with `--no-ff`, in pull request
   number order. A conflicting merge is aborted and that pull request leaves the group.
3. **Pre-flight, seconds, no tests**, on the integrated tree: `ruff`, the quality ratchet against
   `base`, `agent-os-tests check`. It catches sums no single pull request shows (two files added to a
   folder at its limit) before any CI is spent.
4. Push `integration/<UTC stamp>` and open an **integration pull request** against the default branch,
   body listing each member and its pinned head. It has no `Closes #N` and is never merged. A pull
   request, and not a local run, because CI is `on: pull_request` and the host's CI -- its runners, its
   environment -- is the merge check (`2026-10-11-a-green-pr-holding-main-is-the-merge-check-and-the-full-suite-runs-on-a-clock.md`).
5. **One CI, the union selection.** Nothing new computes it: the paths are disjoint, so the diff
   `base...integration` is the union of the members' diffs, and `agent-os-tests plan` selects by path,
   which is monotone: its plan contains every member's. If the four-hour clock is due, the integration
   pull request is simply the next pull request and carries the full run; the integrator does not
   second-guess the plan.
6. **Land.** When every check of the integration head is SUCCESS, each member merges **natively**, in
   number order, with `project.merge_method` (a merge commit in this repository, never a squash:
   the subtree pull of a host needs the merge commit's metadata) pinned to its head, through
   `safe_merge.sh --group <integration PR>`. That mode keeps every refusal of `safe_merge.sh` except
   "head does not contain origin/main", which it replaces by what that rule protected: the integration
   head is green and contains this member's pinned head; `origin/main` is still `base` or the merge
   commit of the previous member (nobody else merged in the middle); the member's head is the pinned
   one. Each member keeps its own merge commit, its `Closes #N` and its audit line, and no merge
   starts a CI. After the last one, `tree(origin/main)` must equal `tree(integration head)`: a
   difference stops the rest and pages the human, because `main` then holds a combination nobody tested.
7. Close the integration pull request without merging, with a comment listing what landed; delete its
   branch; release the lock.

### When a group fails
Pre-flight or CI red. The failing tests are read through the suite's index (never the raw log) and
attributed mechanically: a test belongs to the member whose own plan selects it; a ratchet or manifest
finding names its paths.
- Exactly one member implicated: it goes solo (today's flow), the rest are rebuilt and proved once
  more. At most once per round.
- Anything else (several members, none, a test no plan selects, a timeout, an infrastructure red): the
  whole group returns to one at a time, and the round is recorded as failed.

No bisection. A failed round costs one extra CI and a passed round of N saves N-1, so grouping pays
while fewer than N-1 of every N rounds fail (for pairs, fewer than one in two). A group of disjoint,
judged-independent pull requests that nevertheless fails is a sign the judgment or the rules were wrong,
and that is worth more recorded than a cleverer retry; each bisection level would also add a CI in
sequence.

### How a host configures it
An optional top-level `integrator:` section of `config/agents.yaml` (#206), every key with a default:

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `false` | Off until the ledger shows it pays; a host that pulls the subtree changes nothing. |
| `max_group_size` | `5` | The most pull requests that can be ready together (a host runs up to five workers). |
| `solo_paths` | `[]` | Globs a host adds to the built-in solo list (`.github/**`, dependency manifests and lockfiles, `Dockerfile*`, `bootstrap.sh`). |
| `ci_wait_max_minutes` | `30` | Beyond it the round counts as failed and returns to one at a time. |
| `judge` | `true` | `false`: groups by the mechanical rules alone, a host's explicit choice. |

The role is a one-shot class, `classes.integrator`, like the interpreter's (one turn, no tool); its
model is that class's `model`. Nothing in the mechanism names a host's paths: a host-specific shared
file is a `solo_paths` entry, never a literal in code.

### Which model
Script for everything mechanical: eligibility, grouping, building, pre-flight, waiting, attribution,
landing, the ledger. The LLM judges only independence, in one turn, on **Haiku 5.5** by default
(`classes.integrator.model`): the owner's decision of 2026-10-10 puts simple tasks on Haiku, and the
error is asymmetric (a wrong "no" costs speed; a wrong "independent" is caught by pre-flight and the
integration CI at the price of one CI). Whether Haiku does this at the quality of Sonnet is a doubt of
how, the same one `fr-merge-work-is-not-reviewed-twice` carries as an open spike, so it is settled by an
experiment and not by an estimate (`dec-a-doubt-of-how-is-settled-by-an-experiment`): replay pairs of
this repository's merged pull requests against what happened to them, on both models (#214). Changing
the default is one line of config.

### Evidence
Every round appends one line to `.cache/integrator/rounds.jsonl`: members, the script's facts, the
judge's verdicts and model, the outcome (landed, evicted, solo and why), the integration CI's minutes,
and the time from the oldest member's approval to its merge. `agent-os-integrate report` reads it (#212).
A change to the rules or to the judge's prompt is judged by that evidence and the misses become cases
of the replay (`dec-a-method-change-is-judged-by-evidence-from-the-products`).

## Consequences
- Five ready pull requests wait for about one CI instead of five, and the runner runs one integration
  CI where it ran five refresh CIs. The members' own CIs have already run, in parallel, before.
- A merge seat that uses it merges N pull requests in a row: the planner's `pr_merged` edge
  (`2026-09-17-a-merge-is-an-edge-and-the-human-can-wake-the-planner-by-label.md`) advances its remembered `mergedAt` once and wakes at most once.
- An integration pull request is visible to GitHub and therefore to every reader of open pull requests:
  the guard's scans, the planner's PR-to-issue lookup, the control plane's backlog read. They skip head
  branches under `integration/` (#205, built first, before anything creates one).
- Hosts change nothing on a subtree pull: `enabled` is `false`. The first real group is therefore a
  run the owner watches.
- The new pieces are something the owner has not used yet, so they get no new tests
  (`dec-tests-harden-they-do-not-build`): each build issue names its verification (a dry run on the live
  open pull requests, a landing watched by the merge seat) and the existing suite and the four-hour full
  run catch regressions. The code-quality ratchet runs on the integration pull request like on any other
  (`dec-every-pull-request-gets-a-code-quality-review`).

## Review triggers
- More than one in three of the first fifteen rounds ends returned to one at a time.
- A grouped landing leaves `main` red, or the tree-equality check ever fires.
- The experiment of #214 shows Haiku wrong on `independent` by more than one pair in ten against Sonnet:
  the default becomes Sonnet and this ADR gets a dated amendment.

## Rejected alternatives and what is left out
- **Merging the integration branch itself.** The members would be marked merged by GitHub from
  reachability, and what each pull request records (its merge commit, its `Closes #N`, its audit line)
  would be left to that inference; the single merge commit names no member.
- **Proving the group with a local run.** It would run on the operator's machine and not on the host's
  CI, whose green is the merge check; and it would not exercise the CI's own environment.
- **Bisection after a red group.** See "When a group fails".
- **An LLM that forms the groups.** It could not be trusted to refuse; here it can only split, and the
  script alone decides what may ever be together.
- **GitHub's own merge queue.** A platform feature whose availability depends on the repository's plan
  and rules; the mechanism assumes only the `git` and `gh pr` calls it already makes. A host that has it
  may use it instead; this decision does not depend on it.
- **Left for later, not decided here:** speculative stacking (building the next group on the tip of the
  one whose CI is running, a merge train); disjointness by hunk and not by file (two pull requests
  editing different parts of one file are solo for now); more than one integration at a time.
