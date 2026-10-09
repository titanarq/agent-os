# Onboarding v2, rungs 0-3: from an empty repository to a compiled tree

The first four rungs of the ladder in [`../ADOPTION.md`](../ADOPTION.md). Each has the same shape: what,
why (the tree node that backs it), how (generic commands), how it is checked, what failed the first time
and whether that is fixed, and the baseline the first host measured. What only `proyecto_vector` did sits
under **First host**. Times are that host's local clock; USD is what the mechanism's own `runs.tsv` files
recorded (workers, validators, the expert, puntales), never the control thread's tokens.

## Rung 0 - Install

**What.** `agent_os/` as a subtree, `config/agents.yaml`, the GitHub Apps and their permissions, the
labels, the Project board, the interpreter, a CI that reports a check on a host-only pull request, and the
epic that pauses everything. All of it lands in ONE pull request, merged by hand.
**Why.** `dec-v2-wraps-v1`: v2 sits on the v1 substrate, so the substrate's checklist is the install.
`dec-tree-as-repo-files`: the tree is Markdown in the host's repository, not a service.
**How.**
1. Follow [`substrate.md`](substrate.md) steps 7-21 (subtree, config, Apps, labels, board, interpreter,
   worktrees, `agent-os-install`, `agent-os-doctor`) on a branch `chore/adopt-agentos`.
2. v2 keys on top: `tree.root` (where the tree lives), `tree.ticket_budget_class` (a worker class),
   `project.role_apps.expert` (the expert's App, else the planner's), `project.test_command`, and
   `project.prompt_extras` for the puntal contract once there is a shell. Leave `tree.dispatch_by_node`
   off until rung 3 has produced tickets.
3. Create the epic named by `project.tracking_epic` and put `status:agents-paused` on it BEFORE anything
   else: the guard and the planner then stop, whatever is armed later. Never arm the timer in this rung.
4. The planner's and the validator's Apps need Checks, Commit statuses and Actions (read) besides issues
   and pull requests (substrate step 14); the worker's App needs Contents push and pull-request create.
5. `agent-os-doctor` must be green except the notification topic file and the guard timer, which are
   rung "guard" (not yet exercised).
**Check.** `agent-os-doctor` (one line per check, free); the adoption pull request's CI is green on a
workflow that reports a check; `gh pr checks <N>` as each App's token answers, not as the human's.
**First time.** The adoption pull request was red: the mechanism's puntal-bench test assumed the
repository root and the quality ratchet measured the host's `config/agents.yaml` -- fixed (agent-os#133,
#134). The Checks and Commit-statuses permissions went on the worker's App instead of the planner's, so
`issues move N review` failed closed -- fixed: the doctor now probes both Apps (#140). `init` on a
branch left over from before the adoption refused -- fixed (#140). Installed templates assumed `scripts/`
wrappers -- fixed (#140). A private host needs a git credential helper (substrate step 18), still a manual
step. The backend worktree made before the adoption must be recreated from the adopted `origin/main`.
**Baseline.** Subtree add 07-10 20:48 -> adoption merged 22:42 (1 h 54 min, most of it the CI and #133);
0 USD in runs (a Sonnet control subagent did it); 1 pull request, 1 round after #133.
**First host.** A private host repository, two Apps
(`proyecto-vector-claude` worker and expert, `proyecto-vector-planner`), board Project 4, one worker
slot, `max_parallel_issues` 1, test command validating the tree until the stack exists.

## Rung 1 - The owner's goals and their evaluators

**What.** The owner writes the goals of the product and, under each, its evaluators (a command, or a
criterion an agent judges), as nodes under `tree.root`; the owner answers what the expert later asks.
**Why.** `dec-a-goal-without-evaluators-is-a-red-check`: no evaluators, no green tree.
`dec-a-change-to-the-what-is-merged-only-on-the-owners-word`: goals, evaluators and answers merge on the
owner's word, never by an agent's own verdict. `fr-every-goal-carries-its-evaluators`,
`fr-only-the-owner-changes-a-goal-or-an-evaluator`, `uc-write-or-change-a-products-goals-and-evaluators`.
**How.**
1. Write each `goal-*.md` with the owner, in conversation, one goal at a time, evaluators first.
2. `python -m agent_os.product.tree validate --root <tree.root>` until it prints nothing.
3. An agent that transcribes an approval marks the evaluator as proposed until the owner approves, then
   removes the marker and cites the approval as source. Its commit carries `Node-Change: usage`; the
   trailer `owner` is the owner's own commit and is refused on an agent's branch
   (`agent-os-tree trailers --base origin/main --agent-authored`).
4. Merge on the owner's word; `agent-os-sessions guard-what <PR>` exits 1 on a pull request that touches
   the owner's what, which is how a pipeline knows not to merge it.
**Check.** `validate` is clean; every goal lists evaluators; the CI runs `agent-os-tree trailers`.
**First time.** The phrase "hardened in tests" was removed from the three goals' evaluators (the owner
approved it, 08-10). A fourth goal (the web being operable) arrived with its seven evaluators marked as
proposals; the owner approved them, and the marker was removed with the approval as source in the same
pull request before it merged. An agent writing `Node-Change: owner` is now refused (#139).
**Baseline.** 07-10: vector chosen 18:44, three goals with evaluators 20:01, requirements, use cases and
decisions 20:08, owner's answers 20:18 (1 h 34 min, 0 USD, no worker). Fourth goal: its own pull request
(#11), merged 08-10 23:42.
**First host.** Three goals (privacy, publish, contact), 13 requirements, 17 use cases, 8 decisions; the
owner's answers (title length, language, message limits) came in the control thread and were
transcribed by pull request (#5). Question sessions (`agent-os-sessions open`) were not used.

## Rung 2 - The expert populates the tree

**What.** One run of the expert turns the goals into requirements, use cases and foundations, settles the
stack, records what it must ask, and opens ONE pull request on the tree that it never merges.
**Why.** `uc-start-a-new-product` (this rung is its first real run); `dec-a-soft-product-decision-is-the-refiners-and-a-hard-one-the-owners`
(a how it settles itself, a what goes to the owner with a default); `dec-tree-as-repo-files`.
**How.**
1. Open an issue that says what to populate and any language or stack constraint the owner has.
2. `agent_os/bin/agent_task.sh expert <issue> --dry-run`, read the prompt; then without `--dry-run`.
   Launch by hand: nothing runs the expert unattended (`docs/AGENT_OS.md` section 4.9).
3. Read the summary comment on the issue (Populated / For the owner / Decided without the owner /
   Spikes); answer the `what` questions; transcribe the answers in a pull request.
4. Record each how-decision you take on the way with `agent-os-sessions judgment --role R --kind K
   --decision D --scope how`; the judgments log lives in `.cache/judgments/`.
**Check.** `agent-os-tree validate` on the expert's branch; CI green; no `what` question left open
without a default.
**First time.** The driver ran without a worktree of its own and the prompt fixed the language of the
tree, though the host's tree is in another one -- fixed (#136): it refuses without a worktree and the
language is the host's. The expert chose the stack as a how and the owner was still asked to confirm it.
`prompts/expert.md` still says nothing about `touches` (open).
**Baseline.** Two runs, 17 and 7 turns, 0.84 USD, about 10 minutes of runs; merged the same night after
the owner's answers. 39 nodes, 5 foundations, 3 open spikes, 3 what questions.
**First host.** Python 3.12 + Flask, fpdf2, qrcode, zxing-cpp, pytest, bcrypt; all web code under `web/`
(a second expert pass, PR #10, restructured it: touches overlaps 61 -> 2, ratchet 0 violations; the
repository root sits at the ratchet's limit of 12 entries).

## Rung 3 - Compile in waves

**What.** `agent-os-tree compile` renders the dispatch tickets of every dispatchable node, dependencies
first, with `touches` and a verification; the issues are created wave by wave, never all at once.
**Why.** `dec-dispatch-never-runs-two-tickets-on-the-same-code`; `dec-tests-harden-they-do-not-build` (a
build ticket asks for no tests); `dec-top-down-acceptance-is-essential-even-when-judged`;
`fr-a-usable-product-exists-early` (the first wave is the smallest thing that runs).
**How.**
1. `agent-os-tree compile --out-dir <dir>`: renders only, no network, deterministic. Read `compile.json`:
   tickets, escalations (must be 0), waves.
2. Fix the TREE, not the ticket, for each defect: a foundation with `mechanism: pending`, a use case with
   only the generic criterion, a ticket with no `touches`, overlapping `touches` in one wave.
3. Create wave 0 only: `python -m agent_os.issues create --type task --title "<title>" --body-file
   <dir>/<node>.md`, then `python -m agent_os.issues move <N> ready`. Always move states with
   `issues move`, never `gh issue edit`.
4. `python -m agent_os.product.dispatch start-gate <N> [<running issues>]` is read-only and exits 0
   when the ticket may start, else lists the reasons. Set `tree.dispatch_by_node: true` once tickets exist.
**Check.** 0 escalations; every ticket has a node address, concrete `touches` (1-13 paths, no globs),
no generic criterion; `start-gate` is 0 for the wave-0 ticket.
**First time.** Eight defects: a use case did not inherit its container's order (fixed, #137); the slice
dropped the experiments with findings of its ancestors (fixed, #137); no ticket declared `touches` (fixed:
explicit `touches:` field, #141); build tickets demanded tests, dependencies pointed at nodes without a
ticket, foundations were not "implemented and accepted" (fixed, #141); a use case under a foundation was a
foundation by inheritance (fixed, #142); the evaluators paragraph repeats in every ticket (open); a
verification command naming a test that does not exist leaves the worker without instruction (open).
**Baseline.** First render 23 tickets / 0 escalations (use cases would have gone out with the foundations, in alphabetical order); after the fixes 24 tickets in
10 waves; after refining toward puntales 17 tickets in 6 waves (1/4/3/4/4/1). 0 USD; the fixes took the
night of 07-10 to 08-10 (host PR #6 merged 01:02). Each `subtree pull` costs about 24 minutes of the
host's CI waiting.
**First host.** Wave 0 = `fr-levantar-la-web-en-local`; wave 5 = the test session.
