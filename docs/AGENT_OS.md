# The agent operating system

**What Agentos is for (v2).** Agentos lets one person build and evolve software products far beyond
their individual capacity without losing control of what gets built: a system of agents that turns
its owner's goals into a working product, keeps that product faithful to those goals as it grows,
and improves the way it does so with every product. Its goals and requirements are the tree in
`docs/tree/`; the construction plan is `docs/AGENTOS_V2_PLAN.md`. What follows describes the
mechanism as it stands today: the execution substrate (v1) and the product tree (§4.6) v2 is built
on.

A mechanism for running a software project's backlog through headless coding agents on top of
GitHub Issues and a GitHub Project, for a host project (`titanarq/roedor` is the one instance that
exists today) and the one human who owns it.

The mechanism has two layers. The **knowledge layer** is what an agent reads before it acts:
`AGENTS.md` (the host project's rules), `docs/modules/*.md` (current state, one file per module)
and `docs/adr/*.md` (one binding decision per file) — none of this is part of the mechanism itself,
it is what the mechanism points an agent at. The **state layer** is what the mechanism reads and
writes: GitHub issues carrying exactly one `status:*` label at a time, a GitHub Project (v2) whose
`Status` field mirrors that label for a human to look at, and `.cache/` files on disk that are
never versioned. Every actor below reads the state layer and, except for the human, is told to read
only the parts of the knowledge layer an issue names — never the whole repository.

| Actor | What it does | GitHub identity | Model / class (`config/agents.yaml`) |
|---|---|---|---|
| Human | Writes/approves issues, flips `auto-ready`, answers `blocked-on-human`, merges PRs | the one collaborator account (e.g. `MatillaM`) | — |
| Guard | Deterministic tick: budget, liveness, stall, quota, drift-logging, event-writing | acts through whichever identity a driver already minted; posts no comments of its own except the ntfy page | no LLM — pure Python (`agent_os.guard`) |
| Planner | One-shot decision per wake: relaunch, dispatch, launch validator/refiner, page | its own App (`project.planner_app`) | class `planner`, model per `classes.planner.model` (example: `claude-sonnet-5-5`), 40k ctx / $2 |
| Worker (claude) | Writes code for one issue, in its own worktree. The example config describes ONE backend, Claude Code (agent-os#116, `docs/tree/dec-one-backend-claude-code-with-opus-at-the-top.md`); a second one (Qwen Code) stays possible and is the host's own addition | its own App (`project.backends.claude.app`) | classes `mechanical-sonnet` (400k ctx / $5) and `complex-sonnet` (800k ctx / $20), both `claude-sonnet-5-5` in the example |
| Validator | Reviews one PR against its issue's acceptance criteria | `project.role_apps.validator`, falls back to `planner_app` | class `validator`, model per `classes.validator.model` (example: `claude-sonnet-5-5`), 200k ctx / $5 |
| Refiner | Turns a raw/oversized issue into dispatchable sub-issues, or rewrites one in place | `project.role_apps.refiner`, falls back to `planner_app` | class `refiner`, model per `classes.refiner.model` (example: `claude-opus-5`), 200k ctx / $5 |
| Expert | Populates the host's product tree under the owner's goals (small requirement and use-case nodes, experiments, questions with scope and default answer, challenges), settles every question of how itself or by a spike, receives every question before the owner, and opens one pull request on the tree (§4.9) | `project.role_apps.expert`, falls back to `planner_app` | class `expert`, model per `classes.expert.model` (example: `claude-sonnet-5-5`), 200k ctx / $5 |
| Puntal | Answers ONE live UI action of a product whose interface runs before its code does (Agentos v2, §4.7); plans in one model turn with no tool, and the app's code applies what it planned (the slow path's one tool is the app's persistence API) | none: no GitHub identity, no tracker access | class `puntal`, model per `classes.puntal.model` (example: `claude-sonnet-5-5`), 30k ctx / $0.25 **per invocation** |
| CI | Lints and tests every PR (`.github/workflows/ci.yml`) | GitHub Actions | — |

```
systemd timer (5 min) ──> guard tick ──┬─> reconciles state itself: closed ──> done,
                                        │   promote-refined, orphan doing, status:doing
                                        │   restored under a live worker
                                        ├─> writes event file(s) under .cache/planner_events/
                                        └─> wake() ──flock──> planner_task.sh (one claude -p)
                                                                  │
worker's backend CLI exits ──> guard check (exit hook) ──────────┤
                                                                  ├─> resume/relaunch a worker
                                                                  ├─> launch validator (agent_task.sh)
                                                                  └─> launch refiner (on refine_pending)
                                                                      (both DETACHED: the launch returns
                                                                       at once, the run outlives it, and
                                                                       its end comes back as an event)

human ──> issues.py move / labels / comments on GitHub ──> guard's next tick reads them
guard/planner ──(only when nothing can proceed without a human)──> notify.sh ──> ntfy ──> human's phone
```

## 1. The life of an issue

| Origin → Destination | Executor | Trigger | Writes | Code |
|---|---|---|---|---|
| (creation, no label) → `status:refine` | Human, or refiner (splitting a feature) | Human decision, or the refiner creating children | label + Backlog column | `agent_os.issues:1102-1131` (`cmd_move`); `agent_os/bin/agent_task.sh:239-247` |
| **gap**: creation → `status:refine` automatic | nobody | — | — | `cmd_create` (`agent_os.issues:1022-1049`) assigns no `status:*` |
| `status:refine` (structural defect) → refiner runs, stays `status:refine` | Refiner | `refine_pending` event, only if `planner.refiner_unattended: true`; it names the head of the refine queue, closest to dispatch first (`agent_os.lib.refine_queue_rank`: parent carries `labels.auto_ready`, then position in `labels.priorities`, then no open `Blocked by`, then issue number ascending — #32); an issue whose `<!-- refiner-summary -->` the human already replied to is never named (`agent_os.lib.refiner_pass_answered_by_the_human`, agent-os#72) | original body posted as a comment, body rewritten, `<!-- refiner-summary -->` comment | `agent_os.guard:947-972`; `agent_os.lib:399-427` (`needs_refinement`); `agent_os/bin/agent_task.sh:234-247` |
| `status:refine` (otherwise conformant, `## Stages` missing or empty) → refiner writes it, stays `status:refine` | Refiner | same `refine_pending` event — a missing/empty `## Stages` is itself the structural defect `needs_refinement` checks for | `## Stages` checklist written into the body, `<!-- refiner-summary -->` comment | `agent_os.lib` `REQUIRED_SECTIONS`, `parse_stages`, `section_failures` (`stages: no checklist line`); `agent_os/bin/agent_task.sh` refiner RULES; agent_os/docs/adr/2026-09-15-work-is-staged-before-dispatch-and-each-stage-runs-in-a-fresh-process.md (#375) |
| `status:refine` → split into sub-issues `status:refine`, original loses the label | Refiner | same as above | `issues.py create --parent N` + `move refine` per child | `agent_os/bin/agent_task.sh:239-247` |
| split task/bug → original closed `not planned`, its dependents repointed | Refiner, through `issues.py supersede N --by <child>...` (#39) | the refiner split a task or bug (never a feature, whose children are its parts) | every open `Blocked by #N` line rewritten to the children (all of them unless `--route D=child` narrows one dependent), a comment on each dependent, a `Superseded by` comment and a `not planned` close on N; dependents first, so a cut run never unblocks early | `agent_os.issues` `supersede`; `agent_os.lib` `replace_blocker`; `agent_os/prompts/refiner.md` DECIDE THE SHAPE |
| `status:refine` → `status:blocked-on-human` (refiner's doubt) | Refiner | refiner decides | `<!-- refiner-summary -->` + `@__HUMAN_LOGIN__` + move | `agent_os/bin/agent_task.sh:269-280` |
| `status:refine` → `status:ready` (**auto-ready**) | Guard, via `promote_refined` | **every tick** (#365) — no longer a step the planner must remember; a promotion shows up in the same tick's dispatchable scan and reaches the planner as `new_dispatchable` | label + "Ready for AI" column | `agent_os.guard` `tick`/`promote_refined`; predicate `agent_lib.promotable_to_ready` |
| **fixed** (#365): `promote-refined` outside the `tick` | Guard (`tick`) | every tick calls `promote_refined()` (it is idempotent and already tested) | same label + column as the row above | `agent_os.guard` `tick`; the CLI subcommand stays for a manual sweep, and `agent_os/bin/planner_task.sh` no longer asks the planner to run it |
| `status:refine` → `status:ready` (manual) | Human | decision | `issues.py move N ready` | `agent_os.issues:1102-1131` |
| (nothing on the issue changes) → `new_dispatchable` event | Guard (`tick`) | the tick's dispatchable set gained a number the previous tick's did not have — a human labelling `status:ready`, `promote-refined`, a blocker closing, a cut run put back. **Not** rate-limited: an edge happens once (`agent_os/docs/adr/2026-09-16-a-newly-dispatchable-issue-is-an-edge-not-a-condition.md`, #384) | one event file; the set itself in `<planner cache dir>/dispatchable_seen.json` | `agent_os.guard` `dispatchable_scan`, `_write_new_dispatchable_event_if_gained`, `read_seen_dispatchable`/`write_seen_dispatchable` |
| (nothing on the issue changes) → `pr_merged` event | Guard (`tick`) | one or more PRs merged since the last tick's remembered newest `mergedAt` (`.cache/planner/merged_seen.json`), but only when nothing is running AND at least one issue is dispatchable — a merge while a worker is alive, or with nothing dispatchable, still advances the remembered state but writes nothing (the worker's own `worker_finished`, or a later `new_dispatchable`, re-evaluates instead). First tick with no state on disk records it and writes nothing. A `gh` failure never advances the state. The same tick never writes both `pr_merged` and `idle_dispatchable`. **Not** rate-limited: an edge happens once (`agent_os/docs/adr/2026-09-17-a-merge-is-an-edge-and-the-human-can-wake-the-planner-by-label.md`, #413) | one event file, subject = newest merged PR number, detail lists the merged PRs and the dispatchable issues; `merged_seen.json` advanced | `agent_os.guard` `_write_pr_merged_event_if_gained`, `merged_seen.json` |
| `status:ready` → `status:doing` | Driver (`worker_task.sh start`), launched by the planner or by hand | `new_dispatchable` (an issue *became* dispatchable — one tick's latency, no rate limit) or `idle_dispatchable` (a set *sitting* dispatchable with nothing running, rate-limited by `planner.idle_wake_minutes`); an issue whose backend has no worktree (#392), or whose backend's idle worktree is dirty (agent-os#86), is in neither | `issues.py move N doing`, `.cache/worker_<b>.state=STARTED`, `.issue`, `.brief.md` | `agent_os.guard:1078-1101`; `agent_os.lib:366-397` (`is_dispatchable`); `agent_os/bin/worker_task.sh:303-341` |
| **fixed** (#374): `start` refuses past `planner.max_parallel_issues` alive workers, or when an alive worker's issue shares a `module:` label with the one starting | Driver (`worker_task.sh start`), not the planner | `start` invocation | counts alive workers across every slot of every backend in `project.backends` that has a worktree (`agent_lib.py worker-slots`; a backend's own other slots count too, #90); compares `module:` labels via `gh issue view --json labels`; refuses, writing nothing, at or above the cap or on overlap | `agent_os/bin/worker_task.sh` `start`; `planner.max_parallel_issues` in `config/agents.yaml`, `PlannerConfig` in `agent_os.lib`; agent_os/docs/adr/2026-09-15-parallelism-is-a-configured-cap-enforced-by-the-driver.md |
| `status:doing`, stage N/M committed → stage N+1 starts in a fresh process | Driver, from its exit hook | a stage process exits cleanly with a new `stage N/M:` commit landed and the guard's checks pass (agents-paused, quota, and the issue's cumulative cost AND cumulative tokens both under their class caps — either one passed ends the chain, #387) | fresh backend process (new session, never `--resume`), archives the finished stage's `.jsonl` under `.cache/spend/<issue>/` | `agent_os/bin/worker_task.sh` (chaining, `issue_cost_usd`/`issue_total_tokens`/`ceiling_passed`), `agent_os.guard` `check`, `agent_os.lib` `stages_completed`/`cumulative_cost_usd`/`cumulative_total_tokens`; agent_os/docs/adr/2026-09-15-work-is-staged-before-dispatch-and-each-stage-runs-in-a-fresh-process.md (#375) |
| `status:doing` → `status:ai-completed` | Driver (`worker_task.sh open-pr`), called by the worker's own subshell | backend CLI exits on its own | branch push, `gh pr create` (`Closes #N`), `issues.py move N ai-completed` | `agent_os/bin/worker_task.sh:464-543` |
| `status:doing` → `status:blocked-on-human` (no pull request): the branch's `Node-Change` trailers are not what the host's CI requires | Driver (`worker_task.sh open-pr`), before the merge and the push | a commit of the branch that touches the tree root has no trailer git reads (`missing-node-change`, `misplaced-node-change`: the line sits in a paragraph that is not the last one, as when a `Co-Authored-By:` follows a blank line), has two, a value outside the three, or `owner` (`owner-word-by-agent`: the owner's own word, which an agent never writes) | `.state=BLOCKED reason=malformed_node_change_trailer branch=...`, the command's own output as a comment on the issue, `issues.py move N blocked-on-human`; nothing pushed, no commit rewritten. A human rewords the commits and runs `open-pr` again, which rewrites `BLOCKED` to `DONE` | `bin/worker_publication_refusals.sh`, `agent_os.product.tracker.branch_trailers` |
| `status:doing` → `status:blocked-on-human` (no pull request): the branch fails the code-quality ratchet the host's CI runs | Driver (`worker_task.sh open-pr`), after the pre-merge freeze, before the merge and the push | `python -m agent_os.quality --base <base> --root <worktree>` exits 1: a new file or folder over a `quality:` limit, or one already over it that got worse (`--root` is not optional: the driver does not stand in the worktree). Exit 2 (it could not run) is printed and does not refuse: a failure of the tool is no verdict, and CI judges the pull request | `.state=BLOCKED reason=quality_ratchet_failed branch=...`, the violations as a comment on the issue, `issues.py move N blocked-on-human`; nothing pushed, nothing rewritten. A human (or a resumed worker) brings the paths within the limits and runs `open-pr` again. `prompts/worker.md` tells the worker to run the same command before closing a stage | `bin/worker_publication_refusals.sh` (`branch_fails_the_quality_ratchet`) |
| `status:doing`, a stage's process exits without its `stage N/M:` commit → cut, not a completed stage | Driver's exit hook, or the guard's `tick` | clean exit with no new stage commit since the last one, or the mechanical cut reasons in the row below | `worker_cut` event; `WIP: cut by guard` commit if there is uncommitted work to freeze | same as the row below; agent_os/docs/adr/2026-09-15-work-is-staged-before-dispatch-and-each-stage-runs-in-a-fresh-process.md (#375) |
| `status:doing` → frozen (`CUT_BY_GUARD`), label unchanged | Guard (`tick`) | budget exceeded, stall (turns without commit / 3 identical calls), quota exhausted, or silence past the declared cutoff | `worker_task.sh stop`; `WIP: cut by guard (<reason>)` commit; `.state=CUT_BY_GUARD reason=...` | `agent_os.guard:585-602` (`cut_run`), `652-744` (`_tick_backend`) |
| `CUT_BY_GUARD` → `status:doing` (relaunched from the last completed stage) | Planner, via `worker_task.sh resume` | `worker_cut` event | fresh process (never `--resume` of the cut session) starting at the first stage with no `stage N/M:` commit yet, `.state=RESUMED after=guard_cut` | `agent_os/bin/worker_task.sh` `resume` (cap check inline, now counting cut commits across stages); prompt says what a refusal means, `agent_os/bin/planner_task.sh`; agent_os/docs/adr/2026-09-15-work-is-staged-before-dispatch-and-each-stage-runs-in-a-fresh-process.md (#375) |
| **half-fixed** (#362): `resume` refuses past `planner.relaunch_cap` | Driver (`worker_task.sh resume`), not the planner | `resume` invocation | counts `WIP: cut by guard` commits since the branch's fork point from the issue's base; refuses, writing nothing, at or above the cap | `agent_os/bin/worker_task.sh` `resume`; `planner.relaunch_cap` in `config/agents.yaml`, `PlannerConfig` in `agent_os.lib` |
| `status:doing` (worker asked for help) → `status:blocked-on-human` | Planner, on seeing `worker_finished` with `BLOCKED reason=` in `progress.log` | `worker_finished` event | `issues.py move N blocked-on-human` (prompt instruction, not code) | `agent_os/bin/planner_task.sh:172-179`; the worker only writes `BLOCKED` and comments, `agent_os/bin/worker_task.sh:225-230` |
| **fixed** (#365): same, if the planner fails to label it | Guard (`tick`) | an open `status:doing` issue that no LIVE worker's `.cache/worker_<b>.issue` marker names, not `status:blocked-on-human` | one `orphan_doing` event per issue per `planner.idle_wake_minutes`; the planner's rules say what to do with it (back to `status:ready`, or ask the human if the branch carries work) | `agent_os.guard` `orphan_doing_issues`, `_write_orphan_doing_events_if_due`, `_issues_a_live_worker_is_running`; `agent_os/bin/planner_task.sh` |
| `status:ai-completed` (PR open) → validator runs → **approved**: `status:review` | Planner launches validator — DETACHED, so the launch returns at once and the planner's own run ends without waiting for it (#400), and in an environment of its own: no `AGENT_RUN_*` of the run whose `wake` started that planner travels with the launch, so the validator cuts its worktree at the branch's head at its own launch time and writes its own `runs.tsv` row (#475); validator moves the issue | `worker_finished`/`validator_finished`; condition: open PR, no review yet from the validator's App | `gh pr review --approve`; `issues.py move N review` (refused while a CI check of the PR closing N is red or unfinished, `agent_os/product/tracker/pull_request_checks.py`; the validator reads `gh pr checks` first and requests changes citing the failed check) | `agent_os/bin/agent_task.sh:169-199`; trigger `agent_os/bin/planner_task.sh:111-127` |
| `status:ai-completed` → validator → **changes requested**: label untouched, worker relaunched with the review as context | Planner, via `worker_task.sh resume --context` | `validator_finished` | `resume --after manual --context "<review>"` (counts as a relaunch attempt) | `agent_os/bin/agent_task.sh:188-193`; `agent_os/bin/planner_task.sh:133-137` |
| `status:ai-completed` → validator → **doubt**: `status:blocked-on-human` | Validator, directly | validator decides | review starting with `@__HUMAN_LOGIN__` under `## Doubts` + move | `agent_os/bin/agent_task.sh:194-199` |
| (no label changes) → `role_died` event → the planner reads the log and relaunches the role once | Guard (`tick`) detects, planner decides — the same split as `orphan_doing` | a one-shot role's PID dead while `.cache/<role>/<ts>.pid` is still on disk: removing that file is the run's own last step, so one still there is a run that never reached its end. The log of the same stamp tells the two shapes apart — no terminal `result` is `died_mid_run` (nothing it owed was delivered), a `result` with no `<role>_finished` after it is `ended_unannounced` (it may well have delivered). A LIVE run's file is skipped however long it has sat there (#400). The relaunch the planner makes on this event is a launch like any other (#475): its own brief, its own worktree at the branch's head at that moment, its own `runs.tsv` row, and no `AGENT_RUN_*` inherited from the run whose death was just reported | one event per dead run, naming the log; the PID file removed with it, which is what makes this an edge and not a condition — nothing else clears it, so leaving it would wake the planner to the same dead validator every five minutes. Nothing is written to the tracker | `agent_os.guard` `role_run_death`/`dead_role_runs`/`_write_role_died_events`; the detach itself in `agent_os/bin/agent_task.sh` (`agent_detached_run`, `agent_wait_for_own_session`, and `agent_run_environment_names` for the block a launch never carries over, #475); the planner's `role_died` rules in `agent_os/bin/planner_task.sh` |
| `status:blocked-on-human` → label removed + `human_replied` event | Guard (`tick`) | a comment **by the human** (`project.human_login`) newer than the one that set the label — an agent's own comment on the issue it is blocked on never counts, whatever its timestamp: the mechanism's identities are `project.planner_app`, `backends.*.app` and `role_apps.*`, each commenting as `<slug>[bot]`. Until #397 any newer comment counted, and the planner's own "I am waiting for you" on #387 unblocked a question nobody had answered (2026-09-16) | removes the label; sets no other one | `agent_os.guard` `_check_human_replies`/`_latest_human_comment_at`; `agent_os.lib` `is_human_comment`/`mechanism_logins` |
| **gap**: `human_replied` → what the planner does | Planner (LLM) | — | — | the planner's rules have no paragraph dedicated to this event outside the validator-doubt case (`agent_os/bin/planner_task.sh:138-139`); between label removal and the planner's next run the issue carries no `status:*` at all — unless a worker is still ALIVE on it, in which case the same tick puts `status:doing` back (#385 tick side, `agent_guard.restore_doing_label_on_live_runs`) |
| Open issue carries `project.labels.wake_planner` → label removed + `nudged` event | Guard (`tick`) | the label found on an OPEN issue — the tick removes it every time it sees it, whoever set it (a timeline it cannot read leaves it for the next tick). A `nudged` event is written only when the timeline says the human login (`project.human_login`, via `agent_lib.is_human_comment`) set it; a mechanism identity setting it is removed and ignored, so the planner cannot wake itself in a loop. While the tracking epic carries `status:agents-paused` the tick returns before ever reaching this check, so the label stays put until unpaused. **Not** rate-limited: an edge happens once (`agent_os/docs/adr/2026-09-17-a-merge-is-an-edge-and-the-human-can-wake-the-planner-by-label.md`, #413) | removes `project.labels.wake_planner`; one event file, subject = issue number, detail names who set it and when, and points the planner at the latest human comment on that issue for the reason | `agent_os.guard` `_write_nudged_events`; `project.labels.wake_planner` in `config/agents.yaml`; the label is also the sanctioned lever `.claude/agents/control-plane.md` uses to wake the planner early |
| `status:review` → `done` (close) | Human, or the control plane acting in the human's name under its six merge conditions (§2.4, "Duty 4") | human decision, or the control plane verifying all six conditions itself against GitHub and the diff | the human's own merge, or the control plane's REST merge pinned to the verified head with `project.merge_method` (§2.4; no script does this) + `issues.py move N done` closes the issue | confirmed by grep: no script contains `pr merge`; `docs/adr/2026-08-26-the-agent-proposes-the-human-publishes.md`; `agent_os/docs/adr/2026-09-17-the-control-plane-merges-a-pr-in-the-humans-name-under-five-conditions.md`; `agent_os.issues:1102-1122` |
| closed by GitHub's own `Closes #N`, still carrying `status:*` → `done` | Guard (`tick`) | every tick, for every closed issue that still holds a state label (#365) | `issues.py move N done` — strips the label, leaves the closed issue closed, mirrors the board column | `agent_os.guard` `closed_issues_with_status_label`/`reconcile_closed_issues`, through `_move_issue` |
| Claude quota exhausted → fallback to Qwen | Planner | `CUT_BY_GUARD reason=quota` or `quota_changed`; class allows `qwen_fallback_eligible: true`, or a worker launch was refused because the class declares `fallback:` (§3, #95) | redispatch on Qwen (prompt instruction) | `agent_os/bin/planner_task.sh:181-187`; mechanical detection `agent_os.lib:518-533`. **Inert since 2026-09-16**: no worker class runs on Claude, so no worker run can hit a Claude quota wall |
| Quota exhausted, no eligible fallback | Guard, mechanically | `_tick_backend` sees `quota` and the class disallows Qwen | `notify.sh` (ntfy) | `agent_os.guard:724-728` |
| Nothing dispatchable, everything blocked/capped | Planner's own judgment | after acting on its events, everything named is `blocked-on-human` or at its relaunch cap | `notify.sh` (ntfy) | `agent_os/bin/planner_task.sh:199-205` |
| Daily planner-run cap reached | Guard (`wake`), mechanically | `planner.max_runs_per_day` (40) | one ntfy page (`paged-<date>`); events wait for tomorrow | `agent_os.guard:531-541, 560-578` |
| CI red on the PR | CI | every `pull_request` | a GitHub check; touches no label | `.github/workflows/ci.yml:1-68` |
| Tracking epic carries `status:agents-paused` | Human, exclusively | human decision | nothing else adds/removes it; the tick reads it and writes no events at all that tick; `wake` (also reached from a worker's exit hook `check`) reads it too and runs no planner while it is set -- the events it was handed stay on disk | `agent_os.guard:847-866, 1122-1124`; `issues.py move` never touches it (`agent_lib.py:112-121`) |

Fixed since the table above was first written: the one-issue-per-`module:`-label exclusion
between backends was a prompt sentence with no filter until #374 moved it, plus a configured
parallelism cap (`planner.max_parallel_issues`), into `worker_task.sh start`; the relaunch cap
moved into `worker_task.sh resume` the same way in #362. Neither depends on the planner LLM
anymore.

Staged execution (#375) moves another decision out of the planner's prompt the same way: which
stage runs next, and whether a clean exit counts as a completed stage or a cut, both derive
mechanically from `stage N/M:` commits on the branch (`agent_lib.stages_completed`) rather than
from the planner or the worker declaring progress themselves — the planner only sees the two
ends, `worker_finished` (every stage done) and `worker_cut` (one stage's process ended without its
own commit). `worker_cut` also carries `open-pr`'s own endings, `BLOCKED reason=<reason>`
(`malformed_node_change_trailer`, `quality_ratchet_failed`, `push_rejected`, `workflows_permission`, `merge_failed`): the work is
committed and no pull request exists. The planner prompt says what to do with them: never `resume` the issue and never run `open-pr`
again blindly, make sure the issue is `status:blocked-on-human` (the driver sets it for the first three;
`merge_failed` leaves the issue `doing`, with no comment) and mention the human with the reason.
`tests/product/worker/test_planner_knows_open_pr_endings.py` reads
the reasons from the drivers so a new one cannot go unnamed there.

Transitions nobody performs:
- Issue creation → `status:refine` (a human has to remember to label it; 40/49 open issues carry no `status:*` today).

Fixed by #365, all three on the tick and none of them depending on an LLM: a native GitHub
close-by-merge now reaches `done` on both the label and the board; `promote_refined` runs on every
tick; and an orphan `status:doing` issue raises an `orphan_doing` event instead of at most a
journal line (`_log_state_drift` keeps logging the narrower marker/label mismatch it already
caught — it is still LOG ONLY).

## 2. What the human does, and what they see

### 2.1 Touchpoints

| # | Moment | How they learn about it | Where they look | What they do | If they don't |
|---|---|---|---|---|---|
| 1 | Backlog issue needs to enter the funnel | nothing tells them | `issues.py list` or the board | `issues.py move N refine` (a whole batch at once: `issues.py move N M … refine`) | the issue is simply never touched — nothing else blocks |
| 2 | Approve the refiner's dry run before letting it run unattended | nothing; a decision they make once when reviewing the log by hand | the dry-run log | flip `planner.refiner_unattended: true` (done once, 2026-09-15, `config/agents.yaml:100-105`) | the refiner never runs unattended; `refine_pending` is never written |
| 3 | Put `auto-ready` on a feature | nothing tells them a feature is missing it | the feature's labels | add the `auto-ready` label | every refined child waits indefinitely in `status:refine` |
| 4 | Answer a `status:blocked-on-human` doubt | a `@login` mention in a GitHub comment (issue or PR) — GitHub notifications, not ntfy | the comment | reply there | the issue stays parked with no timeout or second nudge; the rest of the backlog is unaffected except for the backend slot it occupied |
| 5 | Review and merge a PR in `status:review` | an **ntfy push**, once per issue, sent by `issues.py move N review` after the label and the board are written (#366 — the third trigger) | the board, or `issues.py list --label status:review` | `gh pr merge` (no script does this) | PR stays open, issue stays in `status:review`; nothing else blocks, but the work never lands |
| 6 | Authorize the Claude→Qwen fallback for a class | a prior design decision (`qwen_fallback_eligible` in `config/agents.yaml`), not something that happens live | — | set the field | fallback never triggers for that class — which is every class today, since no worker class is on Claude |
| 7 | Re-arm the guard timer after any stop | nothing — never automatic (`docs/runbooks/agent_monitor.md:51-55`) | `systemctl --user status <guard>.timer` | `systemctl --user enable --now <guard>.timer` | nothing fires at all: no ticks, no planner, no promotions, and nothing pages to say so |
| 8 | Pause everything with `status:agents-paused` on the tracking epic | nothing reminds them | — | add the label | — (this is the intended full stop) |
| 9 | Check the state-drift marker in the journal | nothing — it is printed, never an event (`agent_os.guard:1006-1019`, "LOG ONLY") | `journalctl --user -u <guard>.service` | read it | a label/marker mismatch can go unnoticed indefinitely |
| 10 | A staged issue finishes or gets cut mid-stage | the driver's own progress comment on the issue: stages done/total, branch, last commit, whether a `WIP: cut by guard` commit exists (#375) | the issue | read it; on a cut, the planner already decides whether `resume` is worth it, so mostly nothing | the comment stays the only record ON GITHUB — what the issue has spent in tokens is on the machine, in `worker_task.sh <backend> status`'s `issue …` line (#387) or in `.cache/spend/<issue>/` read by hand |
| 11 | A backend's worktree is dirty while no run on it is alive | an **ntfy push** (`backend_worktree_dirty`), once per distinct listing, from the guard's tick; the listing is also printed every tick (agent-os#86) | `git -C <worktree> status` | commit or clean it; untracked files under `scratchpad/` never count, the driver hides that directory from git | that backend starts and resumes nothing: its ready issues are left out of the dispatchable set, and a changes-requested `resume` on it is refused |

### 2.2 The human's day

**Daily, or whenever convenient**: `issues.py list --label status:ready`, `--label status:review`,
`--label status:refine` to see if anything is waiting on a promotion or a merge; a `column -t -s
$'\t' .cache/<role>/runs.tsv | tail` per role for the day's spend; `journalctl --user -u
<guard>.service --no-pager | tail -20` if something smells off (drift, quota).

**Only when paged** (a GitHub mention, or an ntfy push): answer a `status:blocked-on-human` doubt,
or react to one of the three ntfy pages — quota exhausted with no fallback, "nothing can advance",
or a PR that reached `status:review` and is waiting to be merged. Each is a one-line template under
`project.messages`, in `project.human_language`, and no page is written in code (#366).

**Nobody is ever told about**: an untagged backlog, a feature missing `auto-ready`, or a stopped
timer. These are the touchpoints with the least warning of the ten listed above; a PR waiting in
`status:review` left that list on 2026-09-16.

### 2.3 How far the human must go

The human writes or approves the issue (or the refiner's dry run of it), puts `auto-ready` on a
feature to let its children promote themselves, answers whatever gets labeled
`status:blocked-on-human`, and merges the PR. Everything else — dispatch, budget cuts, relaunches,
validation, labeling, board mirroring — is the mechanism's job, not theirs. The one stop lever is
`status:agents-paused` on the tracking epic (`project.tracking_epic`): every tick checks it first
and, while it is set, writes no events at all that tick — a deliberate, human-only full stop, never
something an agent applies to itself.

### 2.4 The control-plane role

The human's side of the flow (§2.1–§2.3) is delegable in part. The **control plane**, defined in
`.claude/agents/control-plane.md`, is the human's delegate over this mechanism: it answers doubts, grooms the backlog, approves and merges validated PRs, and reports on progress and
spend. It does not write issues: an agent definition has one model, and task writing is the
duty that stays on the stronger one, so it is its own definition, `.claude/agents/task-writer.md`
(`project.agent_models.task_writer`, default `sonnet`); asked to write a task, the control plane
says the main thread should use `task-writer`. It never runs a worker or the planner itself — the
mechanism still does that. Every `gh`
call it makes is authenticated as the human (`project.human_login` in `config/agents.yaml`) and
signed with their name, so the bar for any write it makes is *would they do exactly this, given what
is written down?*

Its five duties, in the order the definition gives them:

1. **Write tasks** — scaffold an issue from the template with a budget class and one `module:`
   label, and validate it until `issues.py validate N` says `ok`.
2. **Resolve doubts** — answer a `status:blocked-on-human` question only when an ADR, a module doc,
   the issue body or a dated decisions comment settles it, citing that source; otherwise hand it
   back.
3. **Review and manage the backlog** — classify the untagged issues and *propose* which enter the
   funnel, which need the refiner, which are superseded and which are duplicates; sweep nothing.
4. **Approve and merge PRs** — under the six conditions below.
5. **Monitor progress and deviation** — cheap reads only: the guard timer and its journal, the
   `status:*` labels, the open PRs, `.cache/worker_*.state` and the per-role run/cost files, plus
   each backend's last hour of worker activity; then flag the spend and stall deviations the
   definition lists.

A PR merges only when **all six** of these hold, each one verified by the control plane against
GitHub and the diff rather than trusted from the PR text. `.claude/agents/control-plane.md`'s
"Duty 4" is the binding source for them; what follows restates it:

1. CI is green on the PR's HEAD SHA (`gh pr checks N`), and the PR targets the default branch.
   A head SHA with **zero** checks reported (no check run, no status) fails this condition: the
   control plane does not merge and hands the PR back to the human with that reason. The
   mechanism's side of the bargain is that no PR lacks a check: `agent-os-install` writes
   `.github/workflows/ci-host.yml`, running `project.test_command` on every pull request with no
   path filter (`project.install_host_ci`), because `ci-agent-os.yml` only fires on `agent_os/**`;
   `agent-os-doctor` fails when no workflow would report on a host-only PR
   (`docs/adr/2026-09-24-a-pr-with-no-checks-fails-the-ci-condition-and-every-host-ships-a-ci.md`, agent-os#50).
2. The validator approved it (`gh pr view N --json reviews`) — or no validator review exists and the
   control plane reviewed the diff against the issue's acceptance criteria line by line.
3. The diff (`gh pr diff N --name-only`) touches only files the issue's scope allows, none of the
   merge-audited SUBSET of the host project's forbidden paths — `project.forbidden_paths` in
   `config/agents.yaml` minus `project.merge_audit_exempt_paths`, rendered by
   `agent_lib.forbidden_paths_merge_audit_regex`/`_violations` and the
   `forbidden-paths-merge-audit-violations` CLI subcommand — and nothing that any `AGENTS.md` rule
   freezes. The exemption is narrower than `forbidden_paths` itself, never wider: it names only
   DELIVERY DIRECTORIES (`config/proposals/*`, `docs/adr/*` today), places a PR is meant to add a
   file under whose diff moves no stamp and changes no live configuration, so a worker's brief
   still may never touch one — the exemption is a merge-time reading of the SAME key, not a second,
   looser list a worker could exploit (#476, `docs/modules/workers.md` Contract, "File ownership").
4. No test was removed or weakened: test files compared against the base branch after `ruff format`
   on both sides, by content and not by ancestry (a reflow looks like a deleted assertion, and a
   squash merge is not an ancestor).
5. The PR body closes exactly the issue it was dispatched for, and the module doc changed if
   behaviour or a contract changed.
6. The PR does not touch the owner's what: `agent-os-sessions guard-what N` prints nothing and
   exits 0 (§4.10). A PR that changes a goal node or an evaluator is never merged automatically --
   it waits for the human's own merge. The one exception is a PR whose body says
   `Session-Answer: #S` and for which `agent-os-sessions verify-answer N --session S` exits 0: it is
   exactly the owner's answer, which already is their word
   (`docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`).

When all six hold it merges through GitHub's REST endpoint
(`PUT repos/<project.repo>/pulls/N/merge`) with `merge_method` set to `project.merge_method`
(`merge`, `squash` or `rebase`, default `merge`) and `sha` set to the head it verified, then
deletes the remote branch (`DELETE .../git/refs/heads/<branch>`) only once the merge answered
`"merged": true`. Pinning the SHA means a push after the review makes the merge fail with `409`
instead of riding along; the control plane then re-verifies the new head, it never retries
blindly. REST, not `gh pr merge`, because the latter goes through GraphQL and its secondary rate
limit (agent-os#70). Nothing in the mechanism needs a merge commit — condition 4 compares content,
and `worker_task.sh` only checks the base's ancestry into a branch — so the method is the host's
choice, rendered into the installed prompt as `__MERGE_METHOD__` (agent-os#88). Deleting only the
remote ref also leaves a backend's worktree in place, where `gh pr merge --delete-branch` could
take it with the local branch (§7 row (r)).

If any one of them fails it requests changes with the failing condition and the evidence, leaves
`status:review`, and reports it — it never merges to unblock a round.

Two things always go back to the human. The first is **any question the written record does not
settle**: the control plane does not decide it, it parks it — keeps the label, posts the question
and its options to the human, and says so in its report — because a wrong answer there costs a
whole worker run. The second is the two levers that stay the human's own hand, which it never sets
and never removes: **`status:agents-paused` on the tracking epic** (`project.tracking_epic`) and
**`auto-ready` on a feature**.

## 3. Budget: where it is set, measured, recorded, and where it is not visible

**Where it is set.** The issue template ends with `<!-- budget: <class> -->`
(`.github/ISSUE_TEMPLATE/task.md:26`, `bug.md:27`, default `mechanical-sonnet` in the example config); the class resolves
against `config/agents.yaml`'s `classes:` (`backend`, `model`, `max_context`, `max_cost_usd`,
`max_total_tokens`, `commit_warn_turns`, `commit_cut_turns`, `qwen_fallback_eligible`, and for a worker the optional `fallback` and `escalate`, below). These are
**placeholder numbers today** — the file says so (`config/agents.yaml:6-7`) — real tuning from
recorded runs is a separate, open task in the host project (#342). The five `max_total_tokens`
values are placeholders resting on one measurement rather than guesses: #363, the first real
dispatch, spent 49,526,715 tokens on `mechanical-qwen`, and `mechanical-qwen`'s 80 M ceiling is
1.6× that worst measured case (#390 spent 14,405,623 over four stages, #387 14,265,855 over four of
its five — both re-derived with `agent_lib.py cumulative-tokens .cache/spend/<issue>/*.jsonl`).

**A worker class's launch gate (#95).** `worker_task.sh` asks `agent_lib worker-launch <class>
--backend <its own>` when it launches a stage (`start`, `resume`; a chained stage reads only the
model), on the class the issue's budget line names, and acts on two optional declarations:

- **`fallback: {backend, model, ceilings}`**, the same field a role declares. When the guard's
  persisted verdict on the class's backend reads `exhausted` inside `mechanism.quota_verdict_ttl_minutes`
  (older reads as unknown, exactly as for the roles), the driver **refuses** the launch before any
  side effect (no brief, no `doing` label, no state) and prints the fallback backend, model and
  ceilings. It does not swap the CLI in place: a worker runs in a per-backend worktree with a
  per-backend branch, pidfile, state file, event stream and stream parser, and the branch the
  planner cut for the issue is checked out in that worktree, so the only safe route is the
  planner's redispatch onto the fallback backend's own worktree — the route `qwen_fallback_eligible`
  already uses, now driven by the class's declared `backend`/`model`. `allows_backend_fallback` is
  true for a worker class exactly when it declares `fallback:` (or `qwen_fallback_eligible`), which
  is when a refusal names a way round, so the guard's `quota_exhausted_no_fallback` page stays
  quiet only for a class something can reroute. Only a backend with a `quota:` detector ever has an
  `exhausted` verdict, so a `fallback:` on a `quota: none` backend never triggers.
- **`escalate: {model, after: [commit_cut, stage_failed]}`**, a stronger model on the **same**
  backend for the process `resume` launches after a stage that did not land. The trigger is read
  off the state file the previous process left: `stage_failed` is `CUT_BY_GUARD
  reason=no_stage_commit` (it ran and committed nothing), `commit_cut` is any other
  `CUT_BY_GUARD` except `quota` (a stronger model on an exhausted window is the wrong answer),
  `paused` and `issue_unreadable`. The launch prints `model: <stronger> (ESCALATED: ...)`. A fresh
  `start` and the stages the run chains after a green one run the class's own model again; an
  operator's `WORKER_MODEL` pins the model and outranks both. Escalation is not a way round a
  quota wall and does not count for `allows_backend_fallback`.

On a backend with `slots: N > 1` (#90) the gate reads the backend's verdict and the slot's ending:
the quota verdict is the backend's (`agent_guard_<backend>.json`, shared by every slot), so the
refusal is the same whichever slot would have taken the issue and a free slot of that backend is no
way round it; the previous process's ending is read off the state file of the slot being launched
(`worker_<backend>-<slot>.state` from the second slot on), so a run cut on slot 1 never escalates
the relaunch on slot 2.

Whatever the declarations, the launched model is now the issue's class's own `model` when that class
runs on the backend the driver was dispatched for (before, it was the first worker class on the
backend, whichever class the issue named).

**Unit and who measures it.** Tokens and dollars, never wall-clock time
(`agent_os/docs/adr/2026-09-14-agent-spend-is-tokens-not-time-and-needs-a-written-budget.md`). A turn's size
is `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
(`agent_os.lib:923`, `turn_context_tokens`); a run's token total is the backend's own
terminal `result` event's `usage.total_tokens`, falling back to those four counters summed when it
is absent (`agent_os.lib:934`, `result_total_tokens` — ONE implementation behind both the
`usage-report` RESULT line and the issue-wide sum, so a stage's own report and the ceiling it is
judged against cannot disagree); a run's cost is that same event's `total_cost_usd`
(`agent_os.lib:958`, `usage_summary`) **where the backend reports one at all**. Qwen's does
not: its `result` carries `usage.{input_tokens,output_tokens,cache_read_input_tokens,total_tokens}`
and no `total_cost_usd`, so a Qwen run's cost reads `0.0` — measured, not assumed: `cumulative-cost`
prints `0.0000` over every archived log of #363, #390 and #387, while `cumulative-tokens` prints the
real figures above. The guard compares all three ceilings on every tick
(`agent_os.guard:206`, `budget_exceeded`). Wall-clock time is used only for liveness
(silence versus a declared cutoff), never as a spend ceiling.

**Per stage vs. per issue, under staged execution** (agent_os/docs/adr/2026-09-15-work-is-staged-before-
dispatch-and-each-stage-runs-in-a-fresh-process.md, #375): `max_context` is the ceiling for one
stage's own fresh process — a fresh process, a fresh ceiling, never carried over from the
stage before it. `max_cost_usd` and `max_total_tokens` are BOTH ceilings for the WHOLE issue, the
sum of every one of its stage processes' `total_cost_usd` / `usage.total_tokens`
(`agent_os.lib:754` `cumulative_cost_usd`, `:767` `cumulative_total_tokens`), read over the
finished stages' `.jsonl` files archived under `.cache/spend/<issue>/` plus the live one —
the same file the driver archives into right before chaining to the next stage. ONE listing feeds
both sums on each side (`agent_guard.issue_stage_logs`, `worker_task.sh` `issue_spend_logs`), so the
dollar ceiling and the token ceiling can never be measured over a different set of stages.

Two issue-wide ceilings are not redundancy (#387): on a Qwen class the dollar one can never be
crossed, because the figure it sums does not exist in that backend's stream, and before the token
ceiling existed `budget_exceeded`'s dollar half measured `0.0` for the whole life of every worker
issue — an inert backstop on the backend every worker runs on
(`agent_os/docs/adr/2026-09-16-workers-run-on-qwen-and-claude-only-reviews.md`). Dollars stay because the
three Claude roles do report them, and a second ceiling costs nothing. **Both issue-wide sums
UNDERCOUNT a stage whose own terminal `result` carries no tokens**: a log with no terminal `result`
event contributes 0, which is the honest reading (nothing corroborates the tokens in it) and exactly
the case a runaway issue is made of — measured over #363's ten stage logs, three have no terminal
`result` at all and a fourth ends in `error_during_execution` with `usage` reporting zeros despite
12 turns, so four of the ten count 0. Stated in both docstrings rather than papered over with a
per-turn sum; the follow-up is §7 row (v).

**Where it is recorded.**
- Per worker run in progress: `.cache/worker_<backend>.jsonl` (the backend's raw stream; `worker_<backend>-<N>.jsonl` for a backend's slot N > 1, #90), summarized
  by `worker_task.sh status`/`collect` (`agent_os/bin/worker_task.sh:347`, `usage_report`;
  `agent_os.lib:1054`, `_print_usage_report`).
- Per stage, once finished: archived under `.cache/spend/<issue>/` before the driver starts the
  next stage's fresh process — what `cumulative_cost_usd` and `cumulative_total_tokens` sum for the
  two issue-wide checks (#375, #387).
- Per issue, in tokens, printed for whoever is watching: `usage_report` adds one line under this
  stage's own `context` line — `issue     14265855 tokens across every stage of #387  (ceiling
  80000000)` — from `issue_token_line` (`agent_os/bin/worker_task.sh:358`), which is the same sum the
  gate and the guard cut on. Empty, so the report shows only this stage's own numbers, for a run
  that was never staged; the `(ceiling …)` half is left out when the body on disk resolves to no
  class, because `start` already refused that dispatch and a report is not where it is relitigated.
- Per planner/validator/refiner invocation: one line in `.cache/planner/runs.tsv` and
  `.cache/<role>/runs.tsv` (timestamp, context, model, turns, cost) — `agent_os.lib:1034`
  (`planner_run_row`), `agent_os/bin/agent_task.sh:74-80` (`agent_append_run_row`).
- A full, never-truncated log per run: `.cache/planner/<ts>.log`, `.cache/<role>/<ts>.log`.
- Per puntal invocation (§4.7): `.cache/puntal/runs.tsv` (the same five columns), a per-run log
  `.cache/puntal/<ts>-<µs>-<pid>.log` and, beside them, `.cache/puntal/telemetry.jsonl` -- one JSON
  line per invocation with latencies, tokens, cost and tool calls, which is not a spend record but the
  usage record the refiner will consume -- and `.cache/puntal/feedback.jsonl`, the owner's verdict
  on an answer, joined to the telemetry on `invocation_id`.
- Those files are the drivers' own, never a role's (agent-os#33): each planner, validator and
  refiner run is handed `AGENT_RUN_SCRATCH`, an empty `mktemp -d` directory under `$TMPDIR`
  (outside the run dir and the checkout) for its working files, and the driver removes it on every
  exit path of the run (`agent_make_run_scratch`/`agent_remove_run_scratch` in
  `agent_os/bin/agent_task.sh`). The role prompts name it and forbid writing, moving or deleting
  anything under `.cache/` — a refiner that tidied up with `rm -rf .cache/refiner` had taken the
  run log, the PID file `role_died` reads and every `runs.tsv` row with it.
- **No comment on the issue or the PR carries the cost** — spend lives only in `.cache/`, which is
  gitignored and invisible from GitHub itself, and in the driver's own cut message: a stage gate
  that refuses to chain on budget prints what it measured, `spent $0.0000 of $5.0 and 80000001 of
  80000000 tokens`, so the reason survives in the log even though the dollars read zero.

**What happens on overrun.** Passing ANY ceiling gives the same outcome, `reason=budget`, and two
places check: the guard's tick cuts a live run (`CUT_BY_GUARD reason=budget`), freezes the work in a
`WIP: cut by guard (budget)` commit, and leaves relaunching to the planner — it never retries by
itself and never raises a ceiling (`agent_os.guard:655` `cut_run`, `:781` `_tick_backend`);
and the driver's stage gate, which does not kill anything but refuses to chain the next stage, so an
issue that passed a ceiling stops at the boundary it is already at (`agent_os/bin/worker_task.sh`
`stage-exit`, "THE GATES, IN THIS ORDER": the human's full stop, then the backend's quota, then
either ceiling — `ceiling_passed` on `issue_cost_usd`/`class_ceiling max_cost_usd` and on
`issue_total_tokens`/`class_ceiling max_total_tokens`). An empty ceiling passes nothing: the gate
cuts on a measurement, never on the absence of one.

| Where can I see spend today? | Exists? | Where |
|---|---|---|
| Per run | Yes | the run's log, its `runs.tsv` row, or `worker_task.sh <backend> status`/`collect` while live or just-finished (once `stage-exit` has emptied the live log, `status` shows the newest archived stage of the issue) |
| Per issue (summed across every stage's `start`/`resume`) | **In tokens, yes; in dollars, partially** | `agent_lib.cumulative_total_tokens` and `cumulative_cost_usd` sum the same listing — `.cache/spend/<issue>/*.jsonl` plus the live one (#375, #387). The TOKEN sum is printed for a human by `worker_task.sh <backend> status`/`collect` (one `issue …` line under the stage's own `context`, its ceiling beside it) and by the stage gate's own cut message; the DOLLAR sum still needs the CLI subcommand run by hand (`agent_lib.py cumulative-cost …`) and reads `0.0000` on every Qwen issue. No comment on the issue or the PR carries either |
| Per feature | **No** | nothing joins a feature's children to the `.jsonl`/`runs.tsv` rows of their attempts |
| Total versus budget | **One issue, yes; across issues, no** | an issue's own two ceilings are compared automatically in two places — the guard's tick on a live run, the driver's stage gate before chaining (#375, #387) — and `status` prints the token figure beside its ceiling. Nothing sums across issues: `runs.tsv` supports an `awk` for a role's daily total (`docs/runbooks/agent_monitor.md:130-132`) and no equivalent exists for workers |

**What exists to build the aggregate view (gap).** All the raw material is already on disk: the
per-turn cost in each backend's `.jsonl`, the per-invocation cost in each role's `runs.tsv`, the
class name in the issue body (`<!-- budget: ... -->`), and the full log per run. The per-issue sum
exists as code in both units (`cumulative_cost_usd`, #375; `cumulative_total_tokens`, #387) and the
token one is printed by `status`, so what is still missing is the join, not the measure: nothing
sums by feature (via `gh issue view --json parent`) and nothing reports spend to a human on its own
(#367 owns that, and it must read TOKENS — a report built on `cumulative_cost_usd` prints 0.00 USD
for every worker issue, because every worker runs on the backend that reports no cost).

### Quota is per backend, not per model

The guard's quota verdict (`project.backends.<name>.quota`, e.g. `claude_rate_limit`, persisted
under `.cache/`) belongs to a **backend**, never to a backend plus a model. Two classes on the same
backend with different models — the refiner on `claude-opus-5` beside the planner, the validator and
a Sonnet worker class on `claude-sonnet-5-5` — read and write the same verdict. Anthropic's usage
windows may be counted per model family, so it can happen that Opus is exhausted while Sonnet still
has room; the mechanism cannot tell, and an `exhausted` verdict cut on one family parks every role
and worker on `claude` until the verdict expires (`mechanism.quota_verdict_ttl_minutes`), each falling back
per its own `fallback:` where it declares one. This is deliberate and errs safe: a host that wants
the families isolated declares a second backend for the other model (its own `command`, `worktree`
and `quota` entry) and points those classes at it. Nothing else changes: model ids stay opaque.

## 4. What the mechanism consists of

### 4.1 The one directory, and the host's shims

Since #508 the mechanism is **one directory**, `agent_os/`, taken as a unit: copying it out means
copying that directory, and it is consumed through `git subtree`
(`agent_os/docs/adr/2026-09-21-the-mechanism-is-one-directory-extended-by-hosts-and-never-modified.md`). It
carries its own `pyproject.toml`, its own interpreter (`agent_os/bootstrap.sh` → `agent_os/.venv`,
resolved by `agent_os_python()` in `agent_os/bin/_python.sh` and by
`agent_os.cli.agent_os_python()`), and its own tests with their own `conftest.py`. The host's root
— where `config/agents.yaml`, `.cache/`, `.secrets/` and `.github/` live — is resolved from
`$AGENT_OS_HOST_ROOT`, else from the git checkout the call is made from, and never from the
package's own location.

**Inside the directory**, the tree as it is on this branch (`ls -R agent_os --ignore=__pycache__
--ignore=.venv --ignore=tests`, one line added for `tests/`):

```
agent_os/
├── agent_os/                    the Python package
│   ├── cli.py                     agent_os_python()/agent_os_host_root(), the Python side of the
│   │                               same two resolvers agent_os/bin/_python.sh gives the shell side
│   ├── doctor.py                  agent-os-doctor: the first-run checklist, read-only
│   ├── gh_app_token.py            mints a GitHub App installation token per identity
│   ├── guard.py                   the deterministic guard: budget/quota/stall, tick, events
│   ├── __init__.py                package docstring, points at this doc and the one-directory ADR
│   ├── install.py                 agent-os-install: systemd units + copy-if-absent templates
│   ├── issues.py                  tracker CLI over gh: list/show/create/update/validate/move/…
│   ├── lib.py                     config models, dispatch/budget predicates, jsonl event reading
│   ├── product/puntal/            the puntal driver's Python half, a package (§4.7)
│   ├── product/records/           what every v2 log shares: JSON-lines append, the versions a record carries
│   └── render.py                  __TOKEN__ substitution for the agents/*.md templates
├── agents/                      templates for the .claude/agents/*.md prompts
│   ├── control-plane.md
│   ├── task-writer.md
│   └── worker-runner.md
├── bin/                         the shell drivers
│   ├── agent_task.sh              one-shot driver for validator/refiner
│   ├── notify.sh                  pages the project's ntfy topic
│   ├── planner_task.sh            planner driver, one `claude -p` per decision
│   ├── puntal_task.sh             puntal driver, one `claude -p` per UI action (§4.7)
│   ├── _python.sh                 the one interpreter/host-root resolver every driver sources
│   ├── qwen_task.sh               compatibility wrapper (`exec worker_task.sh qwen "$@"`)
│   ├── worker_progress.sh         what the workers have done lately and spent, one screen
│   └── worker_task.sh             worker driver: init/branch/start/status/watch/collect/open-pr/…
├── bench/puntal/                the puntal bench's instrument (and its executor), outside the package (§4.7)
├── bootstrap.sh                 builds agent_os/.venv, installs the package editable; idempotent
├── config.example.yaml          every §4.2 key, filled in for an invented project
├── docs/                        the mechanism's own docs
│   └── AGENT_OS.md                 this document
├── prompts/                     one template per role, rendered by agent_lib.render_prompt
│   ├── planner.md
│   ├── puntal.md
│   ├── puntal_slow.md
│   ├── refiner.md
│   ├── validator.md
│   └── worker.md
├── pyproject.toml               package metadata, the agent-os-* console scripts, its own
│                                  [tool.ruff]/[tool.pytest.ini_options]
└── templates/
    ├── ci-agent-os.yml            CI snippet agent-os-install copies if the host has none yet
    ├── ci-host.yml                host CI running project.test_command on every PR, rendered if absent
    ├── issue_template/            .github/ISSUE_TEMPLATE/{task,bug}.md, copied if absent
    │   ├── bug.md
    │   └── task.md
    └── systemd/                   .tmpl files agent-os-install renders into
        ├── guard.service.tmpl       ~/.config/systemd/user/
        ├── guard.timer.tmpl
        └── override.conf.tmpl
```

`agent_os/tests/` — the mechanism's own suite (17 files, its own `conftest.py`, `golden/` fixtures
and `capture_golden.sh`): guard/lib/tracker/driver/prompt-template/install/doctor tests, fixtures
and `gh`/backend/`git` stubs only, no database, no network — except `test_agent_lib.py`'s
`m2`-fingerprint test, which still imports `roedor` (a sibling task of #507).

**Outside the directory, and copied too:**

| File | Role | Agnostic? |
|---|---|---|
| `.claude/agents/worker-runner.md` | Prompt for the subagent that operates `worker_task.sh` from Claude Code | Yes |
| `.claude/agents/control-plane.md` | Prompt for the subagent that acts as the human's delegate over the mechanism (§2.4), without task writing | Yes |
| `.claude/agents/task-writer.md` | Prompt for the subagent that writes template-conformant task issues (§2.4); its own definition because it runs on its own model | Yes |
| `.github/workflows/ci.yml` | Lint (touched files only), the host's `pytest -m "not db"`, and — since #508 — `bash agent_os/bootstrap.sh` followed by `agent_os/.venv/bin/pytest agent_os/tests -q`; since #512 a further step copies `agent_os/` to a directory outside this checkout, makes that copy a git repository with the copied files committed (`git init`, `git add -A`, one commit — the mechanism assumes git throughout, so a bare `cp -r` is not yet the reproduction `host_root()`'s own fallback expects, and an empty commit checks out nothing for the launch-path tests that cut a real worktree off HEAD), bootstraps it and runs `pytest tests -q` there, proving the suite passes with no roedor checkout on `sys.path` | Yes |
| `.github/ISSUE_TEMPLATE/task.md`, `bug.md` | Issue templates, already carry `<!-- budget: mechanical-sonnet -->` | Yes |

**The host's shims, which are NOT copied out** (a new host writes none unless it wants them):
`scripts/{worker_task,agent_task,planner_task,worker_progress,notify,qwen_task}.sh` and
`scripts/{agent_guard,agent_lib,issues,gh_app_token}.py` — roedor's own compatibility shims, each a
one-line `exec` into `agent_os/`, listed in `mechanism.own_paths` and never in
`project.forbidden_paths`. The `.claude/agents/*.md` definitions do not depend on them: they name the
commands through the `__MECHANISM_DIR__` token (`agent_os`, the vendoring prefix), as
`__MECHANISM_DIR__/bin/worker_task.sh` and `__MECHANISM_DIR__/.venv/bin/python -m agent_os.issues`,
files every host has (stage 1f; before it they named `scripts/worker_task.sh` and
`scripts/issues.py`, which a host that wrote no shims did not have). `agent-os-install`'s guard
unit already fell back to `python -m agent_os.guard tick` when there is no `scripts/agent_guard.py`.

### 4.2 Configuration (`config/agents.yaml`)

| Key | What it is | Example value |
|---|---|---|
| `project.repo` | owner/name of the GitHub repo; read by `issues.py repo_name()` after the `AGENT_OS_GH_REPO` env variable and before `gh repo view` | `titanarq/roedor` |
| `project.tracking_epic` | the management epic whose `status:agents-paused` is the full stop | `12` |
| `project.board_number` | the GitHub Project (v2) number | `1` |
| `project.secrets_dir` | where `<slug>.json`+`<slug>.pem` per App identity live | `.secrets/gh_apps` |
| `project.planner_app` | the planner's own App slug | `roedor-planner` |
| `project.guard_unit` | the systemd `--user` unit base name `agent-os-install` writes and `agent-os-doctor` checks (`<this>.service`, `.timer`, `.service.d/override.conf`); empty refuses both rather than guessing one (#511, was gap §7h) | `roedor-guard` |
| `project.module_docs_dir` | where this project's module docs live, one per `project.modules`; the `__MODULE_DOCS__` token in the rendered `.claude/agents/*.md` prompts (#510, #511) | `docs/modules` |
| `project.human_login` | the one human, substituted into every `@<login>` mention | `MatillaM` |
| `project.human_language` | language for anything addressed to the human (code/docs stay English regardless) | `Spanish` |
| `project.notify_topic_file` | gitignored file holding the ntfy topic string | `.secrets/ntfy_topic` |
| `project.messages` | one one-line ntfy template per page, written in `project.human_language`; rendered by `agent_lib.render_human_message`, which refuses an unknown key | `review_ready`, `quota_exhausted_no_fallback`, `planner_run_cap_reached`, `backend_worktree_missing`, `unreviewed_pull_request`, `backend_worktree_dirty` |
| `project.modules` | the project's own module names, one per `docs/modules/*.md`; the `module:<name>` half of the fixed label set `issues.py` creates | `ingest`, `metrics`, `workers`, … |
| `project.test_command` | the project's own compact test wrapper, injected as `__TEST_COMMAND__` | `scripts/test.sh` |
| `project.merge_method` | how the control plane merges a verified PR: `merge`, `squash` or `rebase`, the `merge_method` of GitHub's REST merge endpoint, rendered into `.claude/agents/control-plane.md` as `__MERGE_METHOD__` (§2.4). Any other value fails the config load (agent-os#88) | `merge` (the default) |
| `project.agent_models` | the `model:` of each `.claude/agents/*.md` definition, rendered as `__CONTROL_PLANE_MODEL__`, `__WORKER_RUNNER_MODEL__` and `__TASK_WRITER_MODEL__` (agent-os#96): `control_plane` (default `sonnet`), `worker_runner` (default `sonnet`), `task_writer` (default `sonnet`), plus `custodian` and `consolidator` (default `opus`: the two roles that run on Opus, rarely -- the roles arrive in Stage 2 of `docs/AGENTOS_V2_PLAN.md`, so for now only the keys and their defaults exist and nothing reads them). Every other role runs on Sonnet. A value is whatever `claude --model` accepts, an alias or a full id, and is opaque to the mechanism: it keeps no allowlist and no price table, and a run's cost is the `total_cost_usd` the CLI reports in its result event. An unknown key fails the config load. The one-shot roles are not here: their model is `classes.<name>.model` | `agent_models: {task_writer: claude-opus-5}` (the defaults are Sonnet for the three definitions, Opus for the two Stage 2 roles) |
| `project.worktree_links` | paths (relative to the host root) symlinked from the main checkout into a fresh worktree — the validator's throwaway one and a worker's on `init` — when the checkout has them and the worktree does not (agent-os#41) | `[.venv, .env]` |
| `project.worktree_setup_command` | a command run by `bash -c` inside a fresh worktree after the links and before any backend starts; non-zero refuses the run (no validator launched, `init` removes the tree and its branch). For a host whose environment is not a root `.venv` — a monorepo's `uv sync`, an `npm ci` (agent-os#41) | empty: nothing runs |
| `project.lint_commands` | the linters the validator runs on the files a PR touches, each with the file list appended, rendered as `__LINT_RULES__`; empty renders no lint bullet (agent-os#41) | empty (`config.example.yaml`: `.venv/bin/ruff check`, `.venv/bin/ruff format --check`) |
| `project.prompt_extras` | one host-owned file per role, whose text is appended verbatim at that role's `__PROJECT_EXTRAS__` extension point in `agent_os/prompts/<role>.md`; every key optional, paths relative to the host root, and a role with no entry renders nothing there. This is where a sentence only the host can write goes, so the mechanism's own templates carry no literal of any project (#509, row (t) below). `agent_lib.render_prompt` refuses a file the config names and the filesystem lacks | `worker: config/agent_prompts/worker.md`, `refiner: config/agent_prompts/refiner.md` |
| `project.worker_environment` | env vars exported into a worker's backend process (e.g. a read-only DB role); the KEYS also render the worker's environment paragraph, names never values | `DATABASE_URL: postgresql+psycopg://roedor_ro:...` |
| `project.forbidden_paths` | the HOST project's protected path globs, which no brief can authorize; one list behind both the ownership-audit regex and the worker's "FILES YOU MUST NOT TOUCH" paragraph (the mechanism's own files are `mechanism.own_paths` below) | `docs/adr/*`, `docker-compose.yml` |
| `project.never_run` | commands no role may run, each with the one-line reason it rests on; rendered into the worker's, the validator's and the refiner's RULES | `--write`, `census-build` |
| `project.backends.<name>` | every backend a worker or a role can run on, by name (#514): `command` (what the drivers run — an absolute path or a bare name; omitted, the `project.executables` entry of the same name, else the name itself; an absolute one is added to `project.executables`), `worktree` (relative to the host root), `app` (the GitHub App a worker on it signs as), `stream` (the registered parser its jsonl events are read with, `claude_jsonl` or `qwen_jsonl`, which also picks the command-line dialect the drivers launch it with) `quota` (the detector whose `exhausted` verdict cuts a live run: `claude_rate_limit`, or `none` — recorded, never cut on) and `slots` (how many workers run on it at once, default 1, #90: slot 1 is `worktree` and `.cache/worker_<name>.*`, slot N is `<worktree>-N` and `.cache/worker_<name>-N.*`; the quota verdict `agent_guard_<name>.json` and the App are shared by its slots, and an exhausted verdict cuts every live one). An unregistered `stream` or `quota`, `slots` below 1, several slots without a `worktree`, and a derived slot name or worktree another slot already has all fail at config load. Nothing in the mechanism compares a backend's name against a literal: the drivers read these fields (`agent_lib backend-value <name> <field>`), a worker's default model is the first worker class on that backend (`backend-model`), and a test override is `AGENT_<NAME>_BIN` / `PLANNER_<NAME>_BIN` / `WORKER_WORKTREE_<NAME>` by derivation. A third CLI is one entry here, plus one module under `agent_os/agent_os/streams/` only when its events are a shape no registered parser reads | the example config declares `claude` only (`{worktree: ../example-claude, app: example-claude, stream: claude_jsonl, quota: claude_rate_limit}`); a host adds a second backend (`qwen`, `stream: qwen_jsonl`, `quota: none`) itself, with its own worker classes and fallbacks. An existing host's config is not touched by a `subtree pull` |
| `project.worktrees`, `project.worker_apps` | **deprecated alias, one release** (#514): the old per-backend maps. When `project.backends` is absent the loader builds it from them — `stream` is the parser named `<backend>_jsonl` when one is registered, else `claude_jsonl`; `quota` is `claude_rate_limit` exactly for a backend whose own name picked `claude_jsonl`, else `none`, which is the guard's pre-#514 rule — and emits ONE `DeprecatedBackendMapsWarning` per process naming `project.worktrees`, `project.worker_apps`, `project.executables` and `project.backends`. When both are present `project.backends` wins and the warning names each ignored key (and each `project.executables.<name>` a backend's own `command` overrides). After load both maps mirror `project.backends`, so a reader that has not moved sees the same values | `qwen: ../roedor-qwen` / `qwen: roedor-qwen` |
| `project.executables` | the absolute path of every external executable the mechanism's units call by bare name, by command name: the backend CLIs (`qwen`, `claude` — the role drivers look up their own backend here too) and the tracker CLI (`gh`) alike. A name with no entry resolves to itself, which is the bare-name PATH lookup the drivers did before, while a config that does not LOAD stops the driver instead of resolving to anything. `agent-os-install` turns every value into a directory on the generated unit's `Environment=PATH=` (`executables_path_prefix()` in `agent_os/agent_os/install.py`), which is why a non-backend command like `gh` belongs here. Not deprecated: it stays the PATH set, and only stops being where a backend's command is read from when that backend declares `command:` | `{}` (`qwen: /home/you/.nvm/versions/node/vXX/bin/qwen`, `gh: /home/linuxbrew/.linuxbrew/bin/gh`) |
| `project.role_apps` | one App slug per non-worker role, falls back to `planner_app` when empty | `{}` |
| `project.labels` | the `status:*` label vocabulary, plus `wake_planner` — not a state, a one-shot request the tick consumes into a `nudged` event (§1); `types`, `priorities` and `module_prefix` are the rest of the vocabulary `issues.py` used to hardcode (`type:*`/`p<n>`/`module:`, §7 row (c)'s sibling, #510) — defaulted to those same values, so no existing config changes behaviour | `refine: status:refine`, …, `wake_planner: wake:planner`, `types: [epic, feature, task, bug]`, `priorities: [p1, p2, p3, p4]`, `module_prefix: "module:"` |
| `project.board_columns` | `state → Project column` map (`blocked-on-human: null`) | `doing: In progress`, … |
| `mechanism.own_paths` | the mechanism's own files: a worker's diff may touch one only when the issue body names that path as the target of the work. Its own section because it travels with the mechanism (§4.1), so a host project does not configure it — one glob, `agent_os/*`, covers the whole directory since #508, plus the host's own shims | `agent_os/*`, `scripts/worker_task.sh`, `.claude/*` |
| `planner.idle_wake_minutes` | rate limit on the `idle_dispatchable`/`refine_pending` events; `pr_merged` and `nudged` are edges and bypass it (§1) | `120` |
| `planner.max_runs_per_day` | hard cap on planner runs, across every event kind | `40` (12 once a round completes unattended) |
| `planner.refiner_unattended` | gates whether `tick` ever writes `refine_pending` | `true` (after a human reviewed a dry run) |
| `tree.root` | the directory of the product tree and the decision ledger (§4.6), relative to the host's root; `agent-os-tree --root` overrides it for one run | `product` (the default) |
| `tree.ticket_budget_class` | the worker class a compiled ticket names in its `<!-- budget: -->` line; must be a worker class (the config fails to load otherwise). Empty makes `agent-os-tree compile` refuse until `--budget-class` says which | `mechanical-sonnet` |
| `tree.ticket_labels` | labels every compiled ticket carries besides its task type label; the initial `status:*` is Phase 2's to decide | `[]` |
| `tree.dispatch_by_node` | `true` makes the host a **v2 host** (§4.6, Dispatch in a v2 host): the guard and `worker_task.sh start` dispatch only tickets that carry a node address, dependencies first, never two on the same code; a worker's brief gains the slice of its node. Off, nothing in dispatch changes | `false` |
| `tree.test_sessions_dir` | where the product writes a test session's file when the owner closes it (§4.11), relative to the host's root unless absolute; `agent-os-sessions test-ingest` reads it. A host sets it to where its product writes | `var/test-sessions` |
| `classes.<name>` | `backend`, `model`, `max_context`, `max_cost_usd`, `max_total_tokens`, `commit_warn_turns`, `commit_cut_turns`, `qwen_fallback_eligible`, optional `role` (`worker`, `validator`, `refiner`, `expert`, `planner` or `puntal`), optional `fallback` / `escalate` (worker launch gate, §3), optional one-line `description` (when to choose this class). The refiner's and planner's prompts render every worker class -- name, backend, model, description -- at `__WORKER_CLASSES__`, so a host's `prompt_extras` never names a model; `agent-os-doctor` warns when a `prompt_extras` file names a class `classes:` lacks (#97) | see §3 |
| `board.*` | the progress board's GitHub Project (§4.6), all optional: `owner` (`@me`), `number` (0: found by `title`, created on a real sync), `title`, `progress_field`, `order_field` |
| `puntal.*` | the puntal driver's settings (§4.7), all optional: `persistence_command` (the app's persistence API, a shell-split command; the driver refuses to run without one -- here, in `PUNTAL_PERSISTENCE_COMMAND` or in `--persistence-command`), `persistence_api_file` (a text file describing its subcommands, rendered into the contract of both paths: the slow path calls it, the fast path reads it as reference for the operations it plans), `executor_command` (the app's executor, a shell-split command that applies a plan's operations atomically; empty makes the fast path refuse unless the caller asks for `--json --plan-only`; `PUNTAL_EXECUTOR_COMMAND` and `--executor-command` outrank it), `read_subcommands` (default `[get, list]`: the only words a node's declared read may start with), `executor_timeout_seconds` (default `30`), `timeout_seconds` (default `90`: a hung-process safety, not a budget), `max_tool_calls` (default `12`: the slow path's loop guard), `effort` (default empty: `claude --effort`). Unknown keys fail the load. The puntal's model and its three ceilings, which bind ONE invocation, are `classes.puntal` (`role: puntal`; a `fallback:` on it is refused at load) | `timeout_seconds: 90` |

### 4.3 Things to create in GitHub

- **Repo** with `gh auth` scopes covering `repo` (issues, labels, PRs, comments) and `project`
  (read/write on the Project v2 board via `gh project item-add/item-edit` and two bounded
  `gh api graphql` queries — the issue's own `projectItems` and the board's single-select fields;
  `issues.py create` adds every new issue to `project.board_number`, #23).
- **Labels**: `type:epic`, `type:feature`, `type:task`, `type:bug`; `status:refine`, `status:ready`,
  `status:doing`, `status:blocked-on-human`, `status:ai-completed`, `status:review` self-create on
  first `issues.py move` (`status:ai-completed` on the first real `open-pr`);
  **`status:agents-paused`, `auto-ready` and `wake:planner` do not autocreate** — `move` never
  touches them, so they must be created by hand, and `agent-os-doctor` checks exactly these three
  (#54);
  `p1`..`p4`; one `module:<name>` per name in `project.modules` (§4.2).
- **Project v2** with a single-select field named exactly `Status` (a different name falls back
  silently to the first single-select the code finds) and six options matching
  `project.board_columns`: `Backlog`, `Ready for AI`, `In progress`, `AI completed`, `Review`,
  `Done`.
- **Issue templates**: `.github/ISSUE_TEMPLATE/task.md`, `bug.md`, copied as-is. Their front-matter
  `title:` (`[task] `, `[bug] `) is also what `issues.py create --type task|bug` puts in front of
  a title that does not already carry it (#15).
- **One GitHub App per identity** (`backends.<name>.app` per worker backend, `planner_app`, and
  optionally `role_apps.validator`/`role_apps.refiner`), permissions deduced from the calls each
  role makes: workers need Issues (read/write), Contents (push), Pull requests (create); the
  planner needs Issues, Pull requests (read), Projects; the validator additionally needs "Pull
  request reviews" (`gh pr review --approve/--request-changes`). The planner's and the validator's
  Apps also need Checks (read) and Commit statuses (read): `gh pr checks` and `issues.py move N
  review` read a pull request's CI, and without them GitHub answers "Resource not accessible by
  integration". No role needs repo administration or Actions permissions.
- **Install** each App on the repo and drop its `.json`+`.pem` under `secrets_dir`.

### 4.4 Things to create on the machine

- The mechanism's own interpreter: `bash agent_os/bootstrap.sh` builds `agent_os/.venv` and
  installs the package into it, editable, with `pytest` and `ruff`. Nothing in the mechanism
  needs the host's own interpreter to exist; the host's one is reached through exactly one
  configured door, `project.test_command`.
- Binaries: `gh` (authenticated), `git`, `python3.12`, `claude` (worker-claude, validator, refiner,
  planner), `qwen` (worker-qwen), `curl` (`notify.sh`), `ruff==0.16.4` (CI), `systemd --user`.
- One worktree per backend — `agent_os/bin/worker_task.sh <backend> init` (#511, was gap §7r):
  idempotent `git worktree add` on a fresh branch from `origin/main` when the configured path has
  no `.git`, plus a `.venv`/`.env` symlink from the host root when either is missing.
- `.secrets/` — `gh_apps/<slug>.json`+`<slug>.pem` per identity, `ntfy_topic`.
- `.env` at the repo root (credentials); `worker_task.sh` symlinks it into a worktree that lacks one.
- systemd `--user` units (`<guard_unit>.service`, `.timer`, `.service.d/override.conf`) —
  `agent-os-install [--dry-run] [--force]` (#511, was gap §7h) writes them from
  `agent_os/templates/systemd/*.tmpl` and `project.guard_unit`/`project.executables`, with
  `ExecStart=` on the mechanism's own interpreter and never the host's `.venv` (#51); never
  overwrites an existing file without `--force`, and never arms, restarts or reloads a unit —
  `systemctl --user enable --now` stays a human decision (`docs/runbooks/agent_monitor.md`). The
  same command also copies `.claude/agents/{control-plane,task-writer,worker-runner}.md` (rendered from
  `agent_os/agents/*.md`, #510, absent until that PR lands — `install` reports "no templates dir,
  skipped" and does nothing else for that step), `.github/ISSUE_TEMPLATE/{task,bug}.md` and
  `.github/workflows/ci-agent-os.yml`, copied as-is if absent, and `.github/workflows/ci-host.yml`,
  rendered from `agent_os/templates/ci-host.yml` with `project.test_command` if absent and
  `project.install_host_ci` is true (the default): a workflow with no path filter, so every PR
  reports at least one check (§2.4 condition 1, agent-os#50). The rendered
  `.claude/agents/*.md` are generated files: `--force` rewrites each one whole and keeps no hand
  edit, so a customization a host needs becomes a `config/agents.yaml` key rendered as a token
  (`project.merge_method` for the control plane's merge, agent-os#88), never a local edit.
- `agent-os-doctor` (#511) reads back the checklist above — `gh auth status` scopes, the labels
  that do not autocreate, the Project v2 `Status` field and its six options, each App's
  `.json`+`.pem`, whether the planner's and the validator's Apps may read CI checks (a probe of the
  check runs and the commit statuses of the default branch's head with each App's own installation
  token), each `project.executables` entry, each worktree, `project.notify_topic_file` and
  the guard timer's `systemctl --user is-active`, and whether any `.github/workflows/*.yml` fires on
  `pull_request` without a path filter (read from its `on:` block only) — one line per check, exit 1 on any failure. It
  never calls `agent_guard.py check` or any other trigger a role reacts to: a manual check would
  re-announce a run that already finished and wake the planner for free.

### 4.5 Not versioned but required

`~/.config/systemd/user/<guard>.{service,timer}` (hand-edited per machine, hardcodes the working
directory and a description string); `.secrets/gh_apps/*.json`+`*.pem`; `.secrets/ntfy_topic`;
`.env`; the two worker worktrees
themselves; `agent_os/.venv` (built by `agent_os/bootstrap.sh`, gitignored by
`agent_os/.gitignore`); every `.cache/worker_*`, `.cache/planner*`, `.cache/<role>/runs.tsv` file
(generated at run time, correctly gitignored).

### 4.6 The product tree and the decision ledger (`agent-os-tree`)

Phase 1 of `docs/AGENTOS_V2_PLAN.md`. The product layer of Agentos v2 describes a host's product as
a **tree** of nodes (global goals, then functional requirements, then use cases) and a **ledger** of
the decisions that bind it, both stored as Markdown files in the host's own repository. The package
`agent_os.product.tree` defines the format, checks it, cuts the slice of it one agent needs and renders
dispatch tickets from the nodes that are ready to be worked. It touches no network and no backend;
creating the issues from what `compile` renders is Phase 2's wiring. The binding decisions on the
format are in `docs/adr/2026-10-04-the-product-tree-and-the-decision-ledger-are-markdown-files-with-a-doctor.md`.

**Layout.** One directory -- `tree.root` of `config/agents.yaml` (default `product`, relative to the
host's root) or `--root DIR` -- holding Markdown files with YAML frontmatter, nodes and decisions
together, in whatever subdirectories the host likes. What a file is comes from its frontmatter
`type` and never from where it sits; its id is its filename without `.md`, so moving a file between
folders breaks no pointer. Files whose name starts with a dot are ignored; everything else under the
root that is not a record is a red check. A worker writes node files back, so the root must not be
in `project.forbidden_paths`.

**Ids** are `<prefix>-<slug>`: the prefix says what the record is (`goal-`, `fr-`, `uc-`, `dec-`),
the slug is lowercase words joined by hyphens, chosen once and never changed. An id encodes no
position in the tree -- re-parenting a node edits one `parent:` line.

**A node** (`type`: `goal`, `functional-requirement` or `use-case`). The description is the Markdown
body; every other field is frontmatter. An unknown field is an error.

| Field | Required | What it is |
|---|---|---|
| `id`, `type`, `title` | always | the address, the kind, one line of name |
| *(body)* | always | the `description`; blank is an error |
| `parent` | functional requirement, use case | the id of its goal (for a requirement) or its requirement (for a use case); a goal has none |
| `sources` | always, at least one | where the node's content comes from: free text |
| `decisions` | optional | ids of the decisions in force on the node; they bind its whole subtree |
| `mechanism` | functional requirement, use case | the solution mechanism as text, or `pending` (lazy materialization: the first agent that needs it resolves it and writes it back into the node in the same PR) |
| `implementation` | required once `hardened` | where the built thing lives: a path, a symbol, a pull request |
| `touches` | optional, default absent | the code the node touches, as paths under the host's root (`["app/sync.py", "app/queue"]`; a directory covers what is under it; one word each, no whitespace, comma or `-->`, and never the root itself). **When present it decides**: the ticket's `touches` marker is exactly this, and the prose of `implementation` and `mechanism` is not read; `touches: []` says the node touches no known code. **When absent**, the paths are derived from that prose, as before: any word with a `/` or a file extension is taken for a path, so `http.client`, `p.ej` or a document mentioned in passing become false "files" that can hold a ticket back or let two collide. Declare `touches` when the prose of a node misleads that guess (`docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`) |
| `reads` | optional, default empty | the state the node's action reads, as read commands of the app's persistence API (`list tickets`, `get tickets {payload.id}`; `{payload.NAME}` is a field of the click's JSON payload). The puntal's pre-helper runs them and puts the output in its brief before the model turn, so the model spends no turn reading (§4.7). An undeclared read is not an error: the puntal takes the slow path and the telemetry marks it |
| `verification` | **a goal needs at least one** (`goal-without-evaluators`); optional on any other node, where it is acceptance when the node has children; a leaf is dispatched with a command, a judged criterion or none (the ticket's acceptance is then judged by an agent); a `command` is **mandatory for a `hardened` node** | list of entries, each **exactly one of** a `command` (exits 0 when the node holds; with an optional `expects`, what a pass proves) **or** a `judge` (a criterion in plain language that an agent judges against what was built); both in one entry, or neither, is a `schema` error |
| `state` | optional, default `pending` | `pending`, `improvised` (a puntal serves it), `implemented` (deterministic code built from the accepted behaviour, no tests yet), `hardened` (tests written from the accepted interactions) (`docs/tree/dec-tests-harden-they-do-not-build.md`) |
| `foundation` | optional, default false | persistence, identity, UI skeleton: built as a normal ticket and never improvised (`foundation-improvised`). It is **implemented and accepted** -- the essential top-down acceptance, then the owner's in the first test session -- before the shell goes live, and its tests come later, when it hardens: foundations follow the same rule as every node (`docs/tree/dec-tests-harden-they-do-not-build.md`). The flag is **per node**: the doctor reads the node's own, so a use case under a foundation requirement that is not flagged itself may be improvised, and `compile` orders with the foundations only the nodes that carry the flag themselves: a use case under a foundation requirement is **not a foundation by inheritance**, because not every use case under one is indispensable and the expert (`prompts/expert.md`) decides it node by node, marking `foundation: true` the ones it judges indispensable (owner, 2026-10-09) |
| `experiments` | optional | what was tried or is still to be found out about the node (`docs/tree/dec-a-doubt-of-how-is-settled-by-an-experiment.md`); replaces `spikes`. Each entry: `kind` (`spike`, `demand-probe`, `question`, `lookup`), `question`, `outcome` (`open`, `feasible`, `infeasible`, `inconclusive`, and `answered` for a question only), `finding` (required unless `open`), `date`, and for a `question` only its `scope` (`what` or `how`, required) and its `default_answer` (required for `what`: it stands until the owner answers). An open `what` question marks the node **not hardenable** |
| `depends_on` | optional | ids of the nodes that must be done first, each once (`docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`); the doctor checks that each exists and that the edges do not loop. `compile` writes it into the ticket and orders the tickets by it, and a v2 host's dispatch starts a ticket only once the tickets of those nodes are closed (see Dispatch in a v2 host) |
| `acceptances` | optional | the test sessions in which the owner accepted this node, `[{session, date}]`, oldest first; written only by `agent-os-sessions test-ingest` (§4.11) and read by the hardening order: what the owner accepted, and how often, says what to consolidate first (`docs/tree/dec-use-orders-hardening-and-the-owner-order-wins.md`). It is evidence, not a change of the what |
| `challenge` | optional | the node is flagged as possibly not finishable (`docs/tree/dec-a-challenge-is-flagged-early-and-the-owner-decides.md`): `reason` (`no-solution`, `no-verification`, `over-cost`) and an optional `explanation`. It marks the node, and every node that depends on it, **not hardenable**; the owner decides whether to go on. Any node may carry it, a goal included |

A goal carries none of `mechanism`, `implementation`, `experiments`, `depends_on`, `foundation` or a
state other than `pending` (a `challenge` it may): it is not something to build. It **must** carry a `verification`, which is acceptance and
never dispatched work: **tests run top-down from the goals.** A goal's verification (and a
requirement's, once it has use cases) is the evaluator that keeps the work under it from drifting;
the tests written bottom-up at the leaves consolidate reliability. A node with children is a
container whether or not it has a verification (see Tickets), so an upper node's verification is
the acceptance of its subtree and never a ticket of its own.

**A verification is a command or a judged criterion.** The top-down acceptance is essential from the
first build and cannot always be checked deterministically, so an entry is either a `command` or a
`judge`: one paragraph, in plain language, that an agent judges (pass or fail, with reasons) against
what was built (`docs/tree/dec-top-down-acceptance-is-essential-even-when-judged.md`). A goal's
evaluators can therefore be written the day the goal is, with no data or code behind them yet
(`docs/tree/dec-a-goal-without-evaluators-is-a-red-check.md`), and a goal with none fails the
doctor. Only a `command` hardens: a `hardened` node needs at least one, because tests harden and a
judged criterion alone is acceptance (`docs/tree/dec-tests-harden-they-do-not-build.md`). Agentos's
own goals carry their evaluators this way, as `judge` entries. Nothing here runs the judge: the
tree only carries the criterion and renders it, labelled as judged by an agent, to whoever works
under it (see the slice and the tickets).

**A decision.** The statement -- what was decided and what it binds -- is the Markdown body.

| Field | Required | What it is |
|---|---|---|
| `id`, `type: decision`, `title` | always | `title` is the decision in one line |
| *(body)* | always | the `statement`; blank is an error |
| `state` | always | `in-force`, `under-review` (still obeyed: "obey while challenging"), `superseded` |
| `superseded_by` | exactly when `superseded` | the successor's id, which must exist |
| `decided` | always | the date; a review trigger can be measured in time |
| `sources` | always, at least one | where the decision was taken |
| `premises` | always, **at least one** | what it stands on; when one stops being true the decision is due for review |
| `rejected_alternatives` | always, at least one | each `option`, `reason`, and `basis`: `stated` when the source argues against it, `implied` when the ledger only infers it |
| `review_triggers` | always, **at least one** | any one firing puts the decision under review; "A, or B" is two entries |
| `friction` | optional | entries accumulated against the decision: `date`, `summary`, optional `node` and `evidence` |

**The doctor** (`agent-os-tree validate`, alias `doctor`) is a red check the way host literals are
(`tests/test_no_host_literals.py`): one line per defect, `<file>: <code>: <what is wrong>`, exit 1
if there is any. `check_tree` (`agent_os.product.tree.checks`) is the one implementation, and a host's own
test command or CI step runs it: add `agent-os-tree validate` to `project.test_command`'s script, or
call `check_tree(load_tree(root))` from a test. It reads one snapshot of the tree, so it does not
check that a state *transition* was legal, nor run a verification. The one rule that reads the repository
(`implementation-path-missing`) runs under `validate`, which finds the repository from the tree root's git
checkout, and when `check_tree` is called with `repository_root`; `compile` and `slice` leave it out, because
a stale pointer in one node's prose must not stop every other ticket.

| Code | A defect when |
|---|---|
| `orphan-file` | a file under the root is neither a node nor a decision: not Markdown, no frontmatter, or a `type` that is none of the record types |
| `bad-frontmatter` | the frontmatter is not valid YAML (a duplicate key and an impossible date included), or not a mapping |
| `schema` | a field is missing, unknown, of the wrong type or empty (a decision's premises, rejected alternatives and review triggers are mandatory and non-empty), or the Markdown body is blank |
| `duplicate-id` | two files claim the same id |
| `id-filename-mismatch` | the `id` is not the filename without `.md` |
| `id-prefix-mismatch` | the `id` does not start with its type's prefix |
| `parent-missing` | a functional requirement or use case has no `parent` |
| `goal-has-parent` | a goal has a `parent` |
| `dangling-parent` | the `parent` is not the id of any node |
| `parent-type-mismatch` | a requirement is not under a goal, or a use case not under a requirement |
| `parent-cycle` | the `parent` pointers loop |
| `goal-carries-work-fields` | a goal carries a work field (`mechanism`, `implementation`, `experiments`, `depends_on`, `foundation`, or a state other than `pending`); `verification` is not one |
| `goal-without-evaluators` | a goal's `verification` is empty: it needs at least one evaluator, a `command` or a `judge` |
| `missing-work-field` | a requirement or use case has no `mechanism` (write `pending` to defer it) |
| `foundation-improvised` | a foundation node is `improvised`: foundations are built as normal tickets, and the shell does not go live until they are implemented and accepted (their tests come later) |
| `hardened-needs-implementation` | a hardened node has no `implementation` |
| `hardened-needs-verification` | a hardened node has no `verification` with a `command`: tests harden, and a judged criterion alone is acceptance, not hardening |
| `implementation-path-missing` | an `implemented` or `hardened` node's `implementation` names a path written from the repository root (`web/app/x.py`, its first folder there) that does not exist: the code moved or was deleted. Built for precision, not recall: bare file names (`entry.html`), dotted words (`http.client`) and paths relative to a folder named earlier in the sentence (`answers/x.py` after `web/app/shell/`) are never judged. Checked only when the doctor is given the repository |
| `dangling-decision` | a node's `decisions` names an id that is not a decision |
| `superseded-decision-in-use` | a node's `decisions` names a superseded decision; the line names the live successor |
| `superseded-without-successor` | a superseded decision has no `superseded_by` |
| `successor-without-supersession` | a decision that is not superseded has a `superseded_by` |
| `dangling-successor` | `superseded_by` is not the id of any decision |
| `successor-cycle` | the `superseded_by` pointers loop |
| `dangling-friction-node` | a friction entry's `node` is not the id of any node |
| `dangling-dependency` | a node's `depends_on` names an id that is not a node |
| `dependency-cycle` | the `depends_on` edges loop; every node on the cycle is named, a node that only depends on one is not |

**Not hardenable** is a property of the model, not a check: `agent_os.product.tree.hardening` (`hardening_blockers(tree, node_id)`, `is_hardenable`) says which doubts keep a node from hardening -- an open `what` question, or a `challenge`, on the node or on anything it depends on, directly or not -- and why. A node's own `has_open_what_question` is the first half. `compile` uses it to say, in a ticket's definition of done, why the node cannot be hardened yet; no ticket ever asks for `state: hardened`.

A reference to a file that exists but failed to load is not also reported as dangling: the target
has its own defect, and one fault is one line.

**The slice** (`agent-os-tree context NODE [--json]`) is the unit of context an agent is handed,
never the tree: the node in full, its ancestors up to the goal (description, sources and the
verification each one carries, labelled as the acceptance the node's work serves and must not
break, in `--json` as each ancestor's `verification` list, and the findings of its
experiments -- `kind`, `question`, `finding`, one line each, those with a `finding` only -- so an
owner's answer or a decided stack reaches every ticket below it, in `--json` as `experiments`), and the
decisions in force on that chain -- the node's own and its ancestors' -- each with its statement,
premises, rejected alternatives, review triggers and the *count* of its friction entries. A
criterion an agent judges is rendered for the node and for every ancestor as a line
`judged by an agent: <criterion>` (one line, its whitespace collapsed); in `--json` every
`verification` entry has a `kind`, and a judged one is `{"kind": "judge", "judge": ..., "label":
"judged by an agent"}` where a command is `{"kind": "command", "command": ..., "expects": ...}`. The node's header also says what it `depends on` (when it does) and whether it is `hardenable`, with what blocks it; its experiments and its challenge have a section each, and `--json` carries the fields plus `hardenable` and `hardening_blockers`. An
`under-review` decision is in the slice labelled "UNDER REVIEW -- still obeyed while it is
challenged"; a superseded one never is. It contains no sibling, no descendant and no decision that
does not bind the node, so its size is bounded by one chain of ancestors however large the tree
grows (the evaluators above are part of the chain, a sibling's or a descendant's never are), and it
is deterministic: the same tree gives the same bytes. It is refused when a file it is
made of fails the doctor (the doctor's lines are printed); a defect elsewhere does not stop it.

**Tickets** (`agent-os-tree compile [--json] [--out-dir DIR] [--budget-class C] [--label L]`)
renders; it creates no issue. A node becomes a ticket when it is a functional requirement or use
case with no children, `pending`, and its mechanism can be resolved (written, or `pending` with no
experiment having found it `infeasible`). **No verification is needed to dispatch**: tests harden,
they do not build (`docs/tree/dec-tests-harden-they-do-not-build.md`), and the essential top-down
acceptance holds even when an agent judges it (`docs/tree/dec-top-down-acceptance-is-essential-even-when-judged.md`),
so a leaf with a command, with a judged criterion or with nothing gets a ticket. One with nothing is
accepted by criteria **derived** from what it is: `judged by an agent: <node> does what its
description says (the Objective above)` -- the validator's rule for such a node -- and then one line
per acceptance criterion each ancestor carries, the nearest first and the goal's evaluators last
(a goal always has at least one): `judged by an agent: with <node> built, <ancestor> still holds:
<criterion>`. It is not refused: a refusal would make the node wait for a specification that use
has not validated yet, which is what the decision removed (`docs/tree/fr-a-usable-product-exists-early.md`:
nothing waits for a complete specification), and the criterion is never empty because the goal
above it has evaluators. The one **escalation** left is `mechanism-unresolvable`: a
pending mechanism an experiment found infeasible is reported and never a ticket. A goal, a node
past `pending`, and a container (any node with children, whether or not it has a verification: its
use cases are the work, and its own verification is the acceptance of its subtree) are skipped.
A ticket has the shape of the repository's dispatchable issues:
`## Objective` (the node), `## Acceptance criteria` (the node's own verification: each command as
"exits 0", each judged criterion as `judged by an agent: <criterion>`), `## Stages` (one to
resolve and write back a pending mechanism, one to implement), `## Context` (the slice, which
carries the verification of every ancestor, judged criteria included, as acceptance not to break),
`## Not included`, `## Dependencies` (`none`, or the nodes it waits for), `## Definition of done`
(the node file written back with `implementation` and `state: implemented`, **never `hardened`**,
and, when `hardening_blockers` says the node cannot be hardened yet, why), then the markers, one
comment line each. **A ticket builds and asks for no test of the node**: tests harden what use has
accepted, they do not build, and foundations follow the same rule
(`docs/tree/dec-tests-harden-they-do-not-build.md`). The implementation stage is verified by the
acceptance criteria and then by the owner's use; the definition of done says in one line that no
test is written for the node, that the project's existing tests must keep passing, and that
documentation is as the project's `AGENTS.md` asks. Its tests are written when the node hardens.

| Marker | Says |
|---|---|
| `<!-- budget: <class> -->` | the worker class (`--budget-class` or `tree.ticket_budget_class`, a worker class, never a guess) |
| `<!-- node: <id> -->` | the **address**: the node the ticket came from |
| `<!-- depends-on: <id>, ... -->` | the node's `depends_on`, present only when it has any |
| `<!-- touches: <path>, ... -->` | the code the node is known to touch, present only when known |

The touched code is the node's `touches` when it declares one (it decides, and no prose is read);
otherwise the paths named in its `implementation` and, once written, its `mechanism` (a path has a
`/` or a file extension; a directory covers what is under it). A node that names no path touches
nothing known, and a component's paths join once the tree has components
(`docs/tree/dec-a-component-has-a-core-and-extensions.md`). Tickets come **ordered by their
dependencies**, a dependency before whatever depends on it (foundations and then id among the
free ones). A ticket's dependencies are its node's `depends_on` **plus those of every ancestor**
(a use case is part of its requirement, so it cannot start before the requirement can), and a
dependency on a container stands for the work under it; a use case under a `foundation`
requirement is not one by inheritance and goes out with the foundations only when it is flagged
itself (the expert decides it node by node). Those effective dependencies are what the ticket's
`depends-on` marker and Dependencies section carry, **as tickets**: dispatch only waits for an open
ticket, so a dependency on a node that never gets one (already `improvised`, `implemented` or
`hardened`, or escalated) is replaced, in its place, by what that node waits for, as many levels down
as there are such nodes (`agent_os.product.dispatch.tickets.ticket_dependencies`); left standing it would
let the ticket start before the foundations under that node. Dependencies that only loop once
inherited make `compile` refuse the tree, in the text, the JSON and the files. The labels are the task type label,
`tree.ticket_labels` and `--label`; every body is checked by `validate_issue_body` before it is
returned, and `compile` refuses a tree the doctor finds anything in. The code is
`agent_os.product.tree.compile` (what is a ticket) over `agent_os.product.dispatch` (the body, the
markers, the output).

**Dispatch in a v2 host** (agent-os#117,
`docs/adr/2026-10-07-a-v2-host-dispatches-by-node-address-dependencies-first-and-never-on-the-same-code.md`,
`docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`). A host is a **v2 host** when
its `config/agents.yaml` sets `tree.dispatch_by_node: true`. In one, and only there, the rules of
`agent_os.product.dispatch.rules` hold, in code and not in the planner's prompt:

- the guard's dispatchable scan (`dispatchable_scan`) leaves out a ready issue with **no node
  address**, and one whose `depends-on` node still has an **open ticket** (dependencies first);
- `worker_task.sh <backend> start` asks `python -m agent_os.product.dispatch start-gate <issue>
  <running issues...>` after the cap and the module exclusion, and refuses (exit 1, one line per
  reason on stderr) an issue with no address, with an open dependency, or whose `touches` paths
  **overlap** those of an issue another worker is running (the same path, or one inside the other's
  directory). `--force` skips it, like the validation next to it. An issue whose node names no code
  collides with nothing: the check cannot know what it does not say.
- the worker's **brief** (`agent_os.issues brief`) ends with the slice of its node
  (`agent-os-tree context <node>`, cut from the tree as it is at dispatch), never the tree.
- `python -m agent_os.product.dispatch headroom [--json]` is the read-only question *can more work
  run at once right now*: for each ready issue it says whether the start gate and the cap would let it
  start (the issues in the doing state are what runs) or why it waits (an open dependency, code shared
  with a running ticket or one ahead of it, or only `planner.max_parallel_issues` / the backend's
  `slots`), then `N could start now; M wait only for the cap`. The planner asks it every run, starts
  every issue it says could start, and comments `headroom: waits only for the cap` on the rest, with no
  page: quota is the only limit (`docs/tree/fr-independent-work-runs-in-parallel.md`).

Roles: the worker writes back to its own node file (`mechanism`, `implementation`,
`state: implemented`, never `hardened`, never a goal, a `verification` or a `challenge`) and reads
no other node; the refiner keeps a ticket's marker lines on every body it writes; the validator
validates against the node's verification, a command it runs or a criterion it judges, in a
context separate from the worker's (the issue, the slice and the diff, never the worker's
transcript), and judges **every** pull request of the branch against the acceptance of its goals and
use cases, not only the last one; the planner never works around a refusal.

**Recording a change: the `Node-Change` trailer** (`agent-os-tree trailers --base REF [--head REF]
[--root DIR] [--agent-authored] [--json]`, agent-os#116, `docs/tree/dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check.md`).
Every non-merge commit that touches a file under the tree root carries exactly one trailer
`Node-Change: usage | rework | owner`: `usage` is feedback from using the product, `rework` a
correction after a validation or a rejection, `owner` the owner's own word. The nodes a change
concerns are the files the commit touches, so the git history is the record of why each node
changed. The command reads git only: it lists the commits of `REF..HEAD` that touch the root and
prints one line per commit with no trailer (`missing-node-change`), more than one
(`multiple-node-change`) or a value outside the three (`unknown-node-change`), exit 1; a range git
cannot resolve, or a root outside a git repository, is an error (exit 1, one line on stderr), never
a pass. A commit whose `Node-Change:` line is present but not in the last paragraph (a blank line
before a `Co-Authored-By:` line) is reported as `misplaced-node-change`, not as missing: git reads
only the last paragraph as trailers, so the line is there and still invisible. The host CI template
(`templates/ci-host.yml`) runs it on every pull request against the base branch; the worker's and the
refiner's prompts say when each value applies.

A freeze commit (`WIP: cut by guard (<reason>)`: the guard's cut of a run, or `open-pr`'s pre-merge
freeze of a finished run's leftovers) is a commit no agent wrote, and when it touches the tree it
carries the trailer too (`agent_os.product.tracker.freeze_commit`, stage 1f; before it the freeze was
the one commit that failed the check of `open-pr` and of the host CI). It cannot know why the node
changed, so it repeats the reason of the branch it freezes -- the nearest `usage` or `rework` among the
commits the branch has and its base lacks -- and says `usage` when there is none; never `owner`. Leaving
the freeze out of the check would leave the nodes it changed with no recorded reason, and the history
is that record (`docs/tree/dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check.md`). A freeze
that touches nothing under the tree root carries no trailer, and a config that does not load costs
the trailer (said on stderr) but never the commit.

`owner` is the owner's word and an agent never writes it: a worker records what it builds as `usage`
(or `rework` when it corrects a rejection), and `--agent-authored` says that an agent wrote the whole
range, so `owner` there is a defect (`owner-word-by-agent`). `worker_task.sh open-pr` always asks it
that way, and the validator runs it on the pull request's branch and requests changes on any line it
prints (`prompts/worker.md`, `prompts/validator.md`).

The worker's own branch is judged by the same question before its pull request exists:
`worker_task.sh open-pr` runs `agent_os.product.tracker.branch_trailers` (the check above over
`tree.root` of the worktree and the ref the branch is measured against, after the pre-merge freeze)
and, when it reports a commit, opens no pull request and pushes nothing. The run ends `BLOCKED
reason=malformed_node_change_trailer`, the issue gets the command's output as a comment and
`status:blocked-on-human`, and the commits stay as the worker wrote them: the driver warns and does
not repair, because rewording a commit already made is a rewrite and `open-pr` rewrites nothing, and
because it is not handed back to the worker either (a stage is a commit the issue's checklist names,
`launch_stage` refuses an issue with every stage committed, and a worker may not rewrite an earlier
commit). A human rewords the commits and runs `open-pr` again. A worktree with no directory at
`tree.root` has nothing to judge.

Agentos's own tree is `docs/tree/`: its goals and functional requirements (the what, with every
`mechanism: pending` until the how is decided), the plan's founding decisions as the ledger's first
entries, and the decisions taken since. `tests/product/tree/test_tree_founding_decisions.py` runs the doctor and
the slicing over it.

**The progress board** (`agent-os-tree board sync [--dry-run] [--json]`, `board order [--out FILE]`;
`agent_os.product.board`) is a GitHub Project (v2) generated from the tree, as a *view*: the files
stay the memory of record (`docs/tree/dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check.md`),
and the Project is never read back except for the owner's order. A **branch** is a functional
requirement; its **parts** are its use cases (a requirement with none is its own one part). Sync
creates one draft item per branch (title `<title> (<fr id>)`; body: the goal, the parts with their
state `pending|improvised|implemented|hardened`, the open `what` questions with their default
answer, the challenges, `depends_on`) and a `Progress` text field with the count of parts by state.
It is **idempotent**: the plan is computed from what the Project holds, so an unchanged tree makes
no `gh` write; a branch is recognised by the `<!-- agent-os-board: <fr id> -->` first line of its
body. An item whose requirement left the tree is reported as an `orphan` and kept, never deleted
(it carries the owner's order). `--dry-run` prints the plan and calls only read-only `gh`
commands. The owner orders the backlog by writing a number in the Project's `Order` field (lower
first; sync creates the field and never writes it); `board order` prints, and with `--out` writes,
`{"ordered": [...], "unordered": [...], "requirements": [...]}` -- the numbered requirements
first, then the rest in id order. Dispatch consuming it is the planner's (#117); the finishing
reliability per branch is left to Stage 2. The token behind `gh` needs the `project` scope; a
missing `gh` or a refusal is one line on stderr and exit 1. This is the one `agent-os-tree`
subcommand that reaches the network.

### 4.7 The puntal driver (Agentos v2)

A **puntal** is the shore that props a building up: the product's interface goes live early, every
action in it is bound to a use case, and an action nobody has implemented yet is answered, live, by a
headless agent instead of by code (`docs/AGENTOS_V2_PLAN.md`, "Puntal layer"). `bin/puntal_task.sh`
is that agent's driver -- a sibling of `worker_task.sh`, founding decision 6. Phase 0 built it as a
tool loop and measured it (`docs/spikes/2026-10-puntal-latency.md`: no-go as it was); Stage 1 (#115)
rebuilt its contract after `docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md`: **the
puntal plans in one model turn and code does everything else.** The binding decisions are in
`docs/adr/2026-10-04-a-puntal-is-a-one-shot-headless-process-under-its-own-class-and-cannot-write-code.md`
(and its dated note of 2026-10-07).

**The four parts of a click.**

1. *Pre-helper (code).* The node declares the state its action reads (`reads:` in its frontmatter,
   §4.6) as read commands of the app's persistence API. The driver runs them in parallel before the
   model starts and puts their output in the brief, under `State loaded for this action`. It is
   tolerant by design: a malformed declaration, a payload field that is missing, a read that fails is
   reported in the telemetry (`declared_reads`) and shown to the model as what it is, never fatal. Only
   the subcommands in `puntal.read_subcommands` (default `get`, `list`) can be declared, so a node file
   cannot make the pre-helper write. `{payload.NAME}` in a read is that field of the click's JSON
   payload, substituted after the command is split into words: one argument, never a shell.
2. *The model turn (no tool).* One `claude -p` with **no tool at all** (`--tools=`) returns the
   **plan**, one JSON object, and nothing else:

   ```
   {"operations": [<operation> ...], "answer": <what the app is told>, "gap": "<optional gap note>"}
   {"needs_state": "<what state it needs and why>"}        # the slow path, below
   ```
   Four operations are the whole vocabulary an app's executor has to understand
   (`agent_os/product/puntal/fast/operations.py` defines and validates them):

   | Operation | Fields | Meaning |
   |---|---|---|
   | `put` | `collection`, `id`, `document` | create or replace a document |
   | `update` | `collection`, `id`, `changes` (non-empty) | merge fields into an existing document |
   | `delete` | `collection`, `id` | remove a document |
   | `allocate` | `counter`, `bind` | the next number of a counter, named `bind` |

   Any string of a later operation, or of the answer, may carry `{{name}}`: the value an earlier
   `allocate` bound. The puntal cannot know a new id, only the app can; it names it and the executor
   fills it in. At most 50 operations; an unknown key, an unknown operation, a placeholder nobody
   bound (or bound later) is a validation error. A markdown fence around the object and a trailing
   `GAP:` line are tolerated. The turn's contract (`prompts/puntal.md`) carries the app's data API
   when the host documents one (`puntal.persistence_api_file`, under the heading `THE APP'S DATA
   API`, introduced as reference only because this turn runs none of its commands): the turn that
   plans the operations is the one that must know what the app stores and how, and it cannot ask
   `--help`. A host that documents none gets no such section.
3. *Executor (code, on the critical path).* The validated operations go to the app's executor, one
   call: `puntal.executor_command` reads `{"operations": [...]}` on stdin and prints
   `{"ok": true, "bindings": {"name": value}}` or `{"ok": false, "errors": [...]}`, exit 0 either way
   (`fast/executor.py`). `ok: true` means all applied, and the bindings fill the answer; `ok: false`
   means **nothing** was applied (atomic) and the errors go back to the puntal for **one retry turn**.
   Any other end -- a non-zero exit, output that is not that JSON, a timeout -- is a crash and is not
   retried (`executor_failed`, exit `6`). The app owns what it derives: the executor, not the
   puntal, keeps summaries and indexes true. `fast/reference_executor.py` interprets the operations
   over any store with five methods (`exists`, `put`, `update`, `delete`, `next_number`, plus
   `transaction()`); `bench/puntal/executor.py` is that over the bench's JSON store. An app that
   applies operations in its own process asks for the plan alone, `--json --plan-only`, below.
4. *Post-helpers (off the critical path).* The response is written and stdout closed **before** the
   telemetry line, the `runs.tsv` row and the gap note are written, so a caller reading to end of file
   is released while they are.

**The two escapes, at most one of each.** A plan the validator rejects, or an executor that refuses
it, costs **one retry turn**: the brief gains `Your previous plan was rejected` with the reasons; a
second rejection ends the invocation (`invalid_plan`, exit `5`; or `executor_failed`, exit `6`), and
nothing is answered. A plan that says `needs_state` costs **one slow turn**: the same brief, the
`prompts/puntal_slow.md` contract and the confined `./state` tool of the layers below, which does
what the node says and answers in the node's own form (a `GAP:` line as before). The telemetry marks
it (`path: "slow"`, `slow_path_reason`) so the node is corrected to declare the read or the step is
hardened. `--path slow` forces that path from the first turn (the Phase 0 baseline). Ceilings bind the
**invocation**: a later turn is run with what the earlier turns left.

**Calling it.** The node slice (the use case and the goals above it; it may open with the
frontmatter that declares its `reads`, which is stripped before the model sees it), the payload and
the relevant persisted state are plain text, from a file or from stdin (`-`).

```
agent_os/bin/puntal_task.sh --action ACTION --node-file NODE.md [--payload TEXT | --payload-file F]
    [--state-file F] [--read 'CMD' ...] [--node-id ID] [--session-id S] [--invocation-id ID]
    [--label KEY=VALUE ...] [--path fast|slow] [--model M] [--effort E] [--timeout SECONDS]
    [--persistence-command CMD] [--executor-command CMD] [--telemetry-file F] [--dry-run]
agent_os/bin/puntal_task.sh --json [--plan-only]           # the shell API, below
agent_os/bin/puntal_task.sh feedback --invocation-id ID --verdict accept|reject|retry [--note T]
    [--retried-as ID] [--telemetry-file F] [--feedback-file F]
```

STDOUT is the response and nothing else, and it is empty unless the run was answered (a string
answer as it is, any other JSON compact); stderr carries the diagnostics. The exit status says how it
ended: `0` answered, `1` the backend failed, `2` not run (refused before anything was spent), `3` the
run broke the contract, `4` a ceiling cut it, `5` the plan was invalid after its retry, `6` the
executor failed, `124` the safety timeout killed it (per model turn). `--dry-run` prints the resolved
launch -- flags, contract, brief with the node's reads really loaded -- and spends nothing. Unlike
the other role drivers it does not detach, mints no GitHub identity, writes no planner event and wakes
nobody: the caller is waiting for the answer on stdout.

**The generic API for a host's shell** (`--json`, `agent_os/product/puntal/json_api.py`): JSON in,
JSON out, independent of the app's stack. One request object on stdin: `action` (required), `node`
(the slice as text, with the optional `reads` frontmatter) or `node_file`, `node_id`, `payload` (any
JSON value), `state`, `reads` (more read commands), `session_id`, `invocation_id`, `labels`,
`retry_of` (the invocation a retry of the owner's replaces), `previous_attempt`
(`{"plan": ..., "errors": [...]}`, a plan the app applied itself and could not) and `actor` (who
clicked: text, anything else is refused as `not_run`; see the environment below). One envelope on
stdout: `invocation_id`, `outcome` (the telemetry's, or `not_run`), `exit_status`, `detail`, `path`,
`answer` (a JSON value or text), `answer_text` (what the plain CLI would print), `operations`,
`bindings`, `applied`, `gap_note`, `retries`. With `--plan-only` the executor is not called: the
operations and the answer come back as the puntal wrote them, placeholders included, for the app to
apply through its own API and fill in (then `previous_attempt` hands a failure back for a retry).

**The environment of the app's commands.** The pre-helper's reads, the executor and the slow path's
`./state` are the app's own commands, run by the driver for one person's click, and neither the plan
nor the operations say who that person is. The contract is one environment variable
(`agent_os/product/puntal/fast/actor.py`), alongside the ones the driver reads:

| Variable | Who sets it | For |
|---|---|---|
| `PUNTAL_ACTOR` | the JSON request's `actor`; else whatever the host's shell exported, passed on unchanged; else unset (the driver never invents an actor) | who acts. The reads, the executor and the slow path's tool all see the same value; the shim exports it itself instead of relying on the backend's tool to pass the environment on. A command in any language reads it, so the operations' shape and the configured command lines do not change: an app that stamps who created a ticket does it in its executor, which keeps derived data the app's and not the puntal's |
| `PUNTAL_PERSISTENCE_COMMAND`, `PUNTAL_EXECUTOR_COMMAND` | the host's shell | outrank `puntal.persistence_command` and `puntal.executor_command`; `--persistence-command` and `--executor-command` outrank these |
| `AGENT_CACHE_DIR` | the host's shell | moves the run's logs, `runs.tsv`, the telemetry and the feedback file |
| `PUNTAL_<BACKEND>_BIN` | a test or a bench | names the backend binary a stub stands in for |

The actor is for the app's commands only: the brief does not carry it, so the model never sees it,
and the telemetry does not record it.

**Owner feedback** (`feedback`). One line in `.cache/puntal/feedback.jsonl` (beside the telemetry
file, or `--feedback-file`) per verdict, keyed by `invocation_id`: `schema`, `invocation_id`,
`verdict` (`accept`, `reject` or `retry`), `note`, `retried_as` (the invocation that replaced a
retried one), `recorded_at`, `action`, `node`, `session_id` and `versions`, **copied from the
invocation's own telemetry record**: a verdict is about that model and that prompt, not about what is
installed when the owner clicks. A verdict on an invocation the telemetry has never heard of is
refused (exit `2`) and writes nothing.

**Versions on every record** (`agent_os/product/records/versions.py`, which the judgments log will
reuse). `versions` is `{"model", "cli_version", "method_version": {"agent_os_commit",
"prompt_digest"}}`. `cli_version` is what the CLI reported at start-up (null for a run that never
started); `agent_os_commit` is `HEAD` in agent-os's own checkout and, in a host, the upstream commit
the `git subtree --squash` was pulled from (the `git-subtree-split:` of the newest pull of that
directory), null when neither can be told -- never a guess; `prompt_digest` is `sha256:` and 16 hex
digits of the **rendered** contract of the turn that produced the answer.

**What it launches.** One `claude -p` per model turn, in a throwaway, empty scratch directory (so no
project `CLAUDE.md`, `.claude/`, `.mcp.json`, memory or git status reaches the context), with the
contract -- `prompts/puntal.md` on the fast path, `prompts/puntal_slow.md` on the slow one -- as the
whole system prompt and the brief -- node slice, action, payload, state passed in, state loaded,
and a retry's or the slow path's extra section -- as the first message. The flags, and why each one
is there:

| Flag | Why |
|---|---|
| `-p --output-format stream-json --verbose --include-partial-messages` | streaming: the driver stamps every event on arrival, which is what makes time-to-first-signal measurable |
| `--safe-mode` | the user's `CLAUDE.md` and rules, skills, plugins, hooks, MCP servers, custom agents, LSP and auto memory stay out of the context. Works with a subscription login (`--bare` does not: it reads `ANTHROPIC_API_KEY` only) |
| `--system-prompt <contract>` | replaces Claude Code's own system prompt wholesale, so the contract is all of it |
| `--tools=` (fast path) / `--tools=Bash` (slow) | the fast path puts no tool in the model's context at all; the slow path puts only Bash, so Read, Write, Edit, WebFetch, Task... are not there to be misused. Written `--name=value`: a variadic option followed by a space swallows the prompt that follows |
| `--permission-mode dontAsk` (+ `--allowedTools=Bash(./state *)` on the slow path) | a call that would ask for approval is denied, so on the slow path the one Bash command that runs is the persistence shim, and on the fast path none runs |
| `--max-budget-usd <classes.puntal.max_cost_usd>` | the CLI's own per-invocation dollar cut |
| `--no-session-persistence` | no transcript is written under `~/.claude` for a throwaway run |
| `--model`, `--effort` | `classes.puntal.model` / `--model`; `puntal.effort` / `--effort` |

`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` is exported to the backend (version checks and telemetry
are start-up latency a person waiting on a click should not pay). The driver also prints, in every
telemetry record, the exact flag list the run was launched with (`launch.flags`).

**How "the puntal never writes code" is enforced**, as far as the CLI allows, in layers
(`agent_os/product/puntal/__init__.py` docstring). On the fast path the model has no tool, so what
changes state is the executor applying operations agent-os validated, and a tool call is itself a
contract violation. The layers below are the slow path's:

1. *Availability*: `--tools=Bash`; no file-writing tool is in the model's context.
2. *Permission*: `dontAsk` plus one allow rule. The shim `./state` -- written into the scratch
   directory by the driver -- runs the app's persistence command from the host's root with whatever
   arguments the puntal gives it, and it is the only command the rule lets through.
3. *Audit*: every `tool_use` is checked as its block closes, before its result can return
   (`audit_tool_call`): it must be Bash, run `./state`, and carry no shell operator, command
   substitution or second line. The first violation SIGTERMs the run's process group; the run ends as
   `contract_violation` (exit 3) and hands the app no response.
4. *Record*: every tool call and its command, every violation, every file found in the scratch
   directory after the run (`scratch_extra_entries`) and the CLI's own count of denied calls
   (`permission_denials`) are in the telemetry, so "the puntal wrote no code" is a query over the
   log, and the bench's summary prints it as a verdict.

**The known hole**: Claude Code auto-approves *read-only* Bash commands (`cat`, `ls`...) whatever the
permission rules say, so layers 1 and 2 do not stop the model reading a file; layer 3 cuts the run at
the first such call and layer 4 records it, but one such command may have run by then. An MCP server
exposing the persistence API as its only tool would close it, and was not used: `--safe-mode` drops
every non-SDK MCP server (read in the CLI's own source, v2.1.289), and without `--safe-mode` the
user's own plugins, connectors and hooks are back in the context.

**Budget class and ceilings.** `classes.puntal` (`role: puntal`) is the budget class. Its three
ceilings bind **one invocation**, not an issue: `max_context` (the largest single turn) and
`max_total_tokens` (all turns) are checked on the live stream and cut the run (`ceiling_cut`, exit
4); `max_cost_usd` is handed to the CLI (`--max-budget-usd`) and checked again on the result;
`puntal.max_tool_calls` cuts a loop. A retry or slow turn is run with the tokens and dollars the
earlier turns left (the invocation's ceilings, not each turn's). `puntal.timeout_seconds` SIGKILLs a
hung process group, per model turn (`timeout`, exit 124): a safety for a person waiting on a click, never a budget
(`docs/adr/2026-09-14-agent-spend-is-tokens-not-time-and-needs-a-written-budget.md`). The numbers in
`config.example.yaml` are placeholders until a measurement on the vector's real actions sets a floor. There is no launch
gate: a puntal never substitutes a backend, and a `fallback:` on its class is refused at load.

**What it leaves.** `.cache/puntal/runs.tsv` (the five columns every role's has, via the same
helper), one log per run `.cache/puntal/<ts>-<µs>-<pid>.log` (never reused: parallel clicks are the
point) with its `.exited` marker, and the telemetry line. `AGENT_CACHE_DIR` moves the first two, as
it does for the validator and the refiner. The log carries the `backend:` header and the raw stream,
and the class is a non-worker role, so **the guard reads a puntal run as one more quota observation**
(`role_log_quota_observations`): a puntal that meets the rate-limit wall updates the backend's verdict
like any role. There is no PID file and the role is not in `ONE_SHOT_ROLES`: no `role_died` event
exists for a run whose caller is waiting for it.

**The telemetry record.** One JSON object per line in `.cache/puntal/telemetry.jsonl` (or
`--telemetry-file`), appended under a lock, for every invocation whatever its outcome. This file is
the telemetry the refiner will consume to choose what to harden into code. Latencies are in seconds
from the moment `puntal_task.sh` was entered -- the click reaching the driver -- so the shell, the
interpreter's start-up and the config load are inside them. `schema` is bumped on an incompatible
change (`2` since Stage 1: one record per invocation, whatever its number of model turns -- `usage`, `cost_usd`, `tool_calls` and the like add up over the turns, and the first-signal milestones are the first turn's).

| Field | Meaning |
|---|---|
| `schema` | the record's version (`2`) |
| `invocation_id` | a UUID, or the caller's `--invocation-id`; the join key to anything the caller keeps |
| `started_at` | UTC, millisecond precision |
| `action`, `node` | the UI action, and the node it is bound to (`--node-id`, else the node file's stem) |
| `node_digest` | `sha256:` and 16 hex digits of the node slice: tells a node that changed between two clicks |
| `session_id` | the APP's session (`--session-id`): groups the clicks of one user session |
| `backend_session_id` | the backend's own session id of this process |
| `labels` | the caller's `--label KEY=VALUE` pairs, free-form (the bench puts `stage` and `step` here) |
| `class`, `backend`, `model`, `effort` | what ran; `effort` is null when the CLI's default was used |
| `path`, `slow_path_reason` | `fast` or `slow` -- the path that answered; for `slow`, why: the plan's own `needs_state` sentence (an undeclared read: correct the node or harden the step), or `forced by --path slow` |
| `versions` | `model`, `cli_version` and `method_version` (`agent_os_commit`, `prompt_digest`): which method produced the record (above); the feedback and the judgments log carry the same object |
| `outcome`, `outcome_detail` | `ok`, `error`, `timeout`, `contract_violation`, `ceiling_cut`, `invalid_plan` (the plan failed validation after its retry) or `executor_failed` (the app's executor refused the retried plan, or crashed), and why |
| `exit_code` | the backend process's, null if it never started |
| `latency_s` | `total` (entry to response ready); `pre_helper` (the node's declared reads loaded; null if it declares none); `executor` (the app's executor; null if it did not run); `python_startup` (entry to the interpreter being ready: shell, imports); `launch_overhead` (entry to the first backend being spawned); `first_event` (first stream line, the CLI's init); `first_message` (first `message_start`); `first_tool_call`; **`first_text_delta`**: the first assistant text delta of any message, which is the **time-to-first-signal** -- the first thing a UI could show; `final_answer_first_delta` (the first delta of the message that carries the answer, after the tool calls); `backend_reported` (the CLI's own `duration_ms`, `duration_api_ms` and `ttft_ms` when it reports them, a cross-check). A milestone that never happened is null |
| `usage` | `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `total_tokens`, `first_turn` (the four counters of the very first turn, before any tool result) and `context_tokens_first_turn` (their context sum: **the context floor of the call**, system prompt, tool definitions and brief), `context_tokens_peak` (the largest single turn) and `turns` (the CLI's own count of model turns inside the processes, null when none reached a `result`); the token counters are sums over the invocation |
| `cost_usd` | the CLI's `total_cost_usd`; under a subscription it is notional (API-equivalent). Null when the run produced no `result` |
| `turns` | one object per model turn (one `claude -p` process): `n`, `kind` (`plan`, `retry` or `slow`), `outcome`, `outcome_detail`, `started_at_s`, `ended_at_s`, `total_tokens`, `cost_usd`, `num_turns`, `prompt_digest` (of the contract that turn ran under) and `backend_session_id` |
| `declared_reads` | the pre-helper's: `declared` (the commands, as the node wrote them), `ran`, `failed` and `problems` (a malformed declaration, a missing payload field, a command that is not a read) |
| `plan` | `operations` (how many the last valid plan had; null when none parsed), `applied`, `retries`, `attempts` (each rejected attempt: `turn`, `stage` = `validation` or `executor`, `errors`, `text`) and `bindings` (what the executor allocated) |
| `executor` | `ran`, `ok`, `crashed` and `errors` of the app's executor |
| `tool_calls` | per call over all turns: `name`, `command` (Bash only), `at_s`, `violation`, `is_error`, `result_chars`; empty on the fast path |
| `tool_violations` | the audit's findings; empty means the puntal ran only `./state` (on the fast path, ran no tool) |
| `init` | what the CLI said it started with: `tools`, `mcp_servers`, `permission_mode`, `claude_code_version` -- evidence the confinement took |
| `permission_denials` | how many calls the CLI itself denied |
| `ceilings` | the four ceilings and the timeout this run was bound by, and `exceeded` (any passed, cut or not) |
| `launch` | `flags` (the first turn's exact confining flags), `persistence_command` and `executor_command` |
| `scratch_extra_entries` | files found in the scratch directory after the run, other than the shim |
| `response` | the response the app received: the answer, placeholders filled (empty text for a run that did not finish) |
| `gap_note` | the *gap note*, below, or null |
| `stderr_tail` | the last non-JSON lines the backend printed, kept only when the run was not `ok` |

**The gap note.** When the action asks for something its node does not describe, the contract tells
the puntal to do the closest safe thing and say so: `"gap": "asked for <what>; the node does not describe it"`
in the plan (the slow path ends its message with a line `GAP: ...` instead). The driver keeps it out of
the response and records it in `gap_note`: the telemetry the refiner reads to
find use cases that need a node written or sharpened.

**The bench and the measurement** (`bench/puntal/`, outside the `agent_os` package and so outside the
wheel: it is an instrument, not mechanism, and nothing imports it). A helpdesk of tickets over a JSON
document store (`store.py`, a CLI of atomic file writes with a locked counter), four nodes bound to
five actions -- `create_ticket`, `change_status`, `show_board`, `board_report`, and `export_csv`
bound to the show-board node that says nothing of exporting, the deliberate gap -- a reference model
of their rules (`domain.py`), a fake `claude` that plays a perfect or a faulty puntal
(`fake_claude.py`, with `fake_fast.py` for the fast path), the helpdesk's executor (`executor.py`: it applies a plan to the store and recounts `summary/board` itself), and `measure.py`:

```
measure.py calibrate --dry-run             # (every stage takes `--puntal-path slow|fast`; `slow`, the default, is the Phase 0 tool loop this bench was built to compare against)
measure.py calibrate --dry-run             # 2 calls -> the context floor: the smallest brief, cold cache; then warm cache + ONE read through the persistence tool
measure.py main --session 1 --dry-run      # 3 sessions of 8 over ONE store, a fresh process per call
measure.py main --session 2                #   (replace --dry-run by --allow-real-calls to spend)
measure.py main --session 3
measure.py reserve --count 2 --model M     # up to 4 adaptive probes on the same store: another model, effort...
measure.py summarize [--json]              # latency, cost, coherence: from the raw files only
measure.py status | check-store
```

Run it with the mechanism's interpreter, `.venv/bin/python bench/puntal/measure.py <stage> ...`: it
imports the package and `pyyaml`. Everything lands in `--workdir` (default `.cache/puntal-bench/`): the shared store, `telemetry.jsonl`
(the driver's records), `trace.jsonl` (the harness's: action, payload and the whole store before and
after each call) and the generated `agents.yaml`. **Real calls are guarded in code**: they need
`--allow-real-calls`; the script refuses under pytest; every real call is counted in a persistent
file (`~/.cache/agent-os/puntal-bench-real-calls.json`, so the count spans checkouts) *before* it is
made, and the 31st is refused -- `REAL_CALL_CAP` is a constant, not a setting; a stage that would not
fit in what remains is refused whole before it starts; a dry run never touches the counter. Before
a real stage's first call it runs `claude --help` and `claude <the driver's flags> --version` -- the
only other commands it ever runs on the real CLI -- to check that every flag is still listed and
every value still accepted; the calibration's second call makes one read through the persistence
tool and the stage stops if that call did not run (a denied or missing tool would fail every action
of every session the same way), and no real session starts before the calibration passed; two
failed invocations in a row stop a stage (one stops the calibration), so a setup that fails
systematically does not burn the cap. The tests stub the backend
and fail if a trap `claude` on PATH is ever reached.

`summarize` reports p50/p95 of full-response latency and of time-to-first-signal (and the other
milestones), cost per action (mean, and tokens), the prompt-cache split, the calibration floor, and
**coherence** from three oracles that blame different things: the store's invariants (sequential ids,
the derived `summary/board` equal to a recount, status and resolution consistent), a one-step replay of
each action's rules from the store as it was before the call, and a ledger replayed from the empty
store and compared with the store at every session boundary -- a fact established in session N that
is no longer true in N+1, or reported differently in N+1, is listed with its evidence. It also says how many invocations took each path, needed a retry turn or were refused by the executor. It states its
own sample size (`p95` of 24 is the 23rd value; one slow call moves it) and that `total_cost_usd` is
notional. It judges the plan's starting points (first signal < 5 s, full response p95 < 30 s, mean
cost < $0.10, zero contradictions) and adds one of its own, that the puntal ran only `./state`.

### 4.8 The code-quality ratchet (`agent-os-quality`)

Every pull request gets two checks on the shape of the code it adds
(`docs/tree/dec-every-pull-request-gets-a-code-quality-review.md`). The first is deterministic and
blocks in CI: `agent_os/quality/` compares the PR head against the **merge-base** with the base
branch and fails when

- a **new** file has more than `quality.max_lines_per_file` lines (default 300), or a **new**
  folder holds more than `quality.max_entries_per_folder` tracked entries (default 12, files and
  subfolders alike); or
- a file or folder that was **already over** a limit got worse: a file grew, a folder gained an
  entry. Staying as it was, or shrinking, passes, so splitting an offender is always allowed.

Only git-tracked entries count. A renamed or moved file is a new file to the check (no rename
detection), so split code by moving its pieces out and keeping the original smaller. Binary files
count no lines. Output is one line per violation; exit 0 clean, 1 violations, 2 the check could
not run (no merge-base: the CI checkout needs `fetch-depth: 0`; a config that does not load).

```
agent-os-quality --base origin/main [--root DIR] [--config PATH]
```

The repository judged is the git checkout the working directory (or `--root`) belongs to, never `AGENT_OS_HOST_ROOT`: the drivers export that variable, the host's main checkout, into every worker's worktree, where reading it measured `main` and answered green for a branch CI fails. Outside any repository the check exits 2.

`open-pr` also lists, in the pull request body, the files the branch changes outside the ticket's `touches` marker (`agent_os.product.tracker.paths_outside_touches`; listed, never refused, `docs/adr/2026-10-09-a-branch-outside-its-touches-is-listed-not-refused.md`), and `prompts/validator.md` asks for a verdict on each.

The `quality:` section of `config/agents.yaml` (`config.example.yaml` documents it) holds
`max_entries_per_folder`, `max_lines_per_file` and `excluded_paths`: data and prose are not code, so
by default `docs/`, `tests/golden/`, `config.example.yaml` and `uv.lock` are not measured and not
entered (an excluded path still occupies one entry of its parent). Always excluded besides the
list: `tree.root`, the host's own `config/agents.yaml` (the config file that was loaded, when it is
inside the repository: configuration is not code), and the mechanism's own directory when it is
vendored under a host (`agent_os/`, which only changes through `git subtree pull`). The mechanism's own CI calls it from
`.github/workflows/ci.yml` and a host's from `templates/ci-host.yml`. The second check is the
validator's: `prompts/validator.md` makes it review the diff for SOLID, long self-explanatory names
and comments only for a non-obvious why, requesting changes like any other finding.

### 4.9 The expert (`agent_os/bin/agent_task.sh expert N`, Agentos v2 Stage 1)

The expert turns the owner's goals into the rest of the tree
(`docs/adr/2026-10-07-the-expert-populates-the-tree-and-settles-a-how-before-the-owner-hears-it.md`).
It is a one-shot role like the validator and the refiner -- class `expert` (`role: expert`, Sonnet,
no `fallback:`), prompt `prompts/expert.md`, App `project.role_apps.expert` else `planner_app`, logs
and `runs.tsv` in `.cache/expert/`, a detached run that ends with an `expert_finished` event -- with
one difference: it writes.

**Launch.** By command only: `agent_os/bin/agent_task.sh expert <issue> [context...] [--dry-run]
[--no-wake]`. The issue is the request (a new product, a question that reached the expert, a part of
the tree to populate); its first run on a new product follows `uc-start-a-new-product`. Nothing
launches it unattended -- no label, no `refine_pending`-style event -- and the planner's prompt says
it never does; a run that died (`role_died`) is the human's to relaunch. The driver fetches the
host's default branch, makes a throwaway worktree off it under `.cache/expert/`, exports
`PYTHONPATH` at it and starts the backend inside it (the one role not started in the main checkout);
the worktree is removed when the run ends. `__TREE_ROOT__` in the prompt is `tree.root`.

**What it writes.** Only files under the tree root, on a branch `expert/<N>-<slug>`, in one pull
request that it opens and never merges: functional requirements and use cases as small nodes under
the goals (`mechanism: pending`, a `verification` whenever one can be written, `depends_on` to order
the foundations first), `experiments` (`spike` recorded `open` with its timebox, `demand-probe`,
`lookup` answered, `question`), and `challenge` where a node may not be finishable. It never touches
a goal, an evaluator or a decision.

**Questions.** It reads every question before the owner. A `how` it settles itself (`answered`, with
the finding) or by an open `spike`; the owner never receives it. A `what` carries a `default_answer`
and goes to the owner. In doubt it is a `what`. Its one summary comment on the issue starts with
`<!-- expert-summary -->` and has up to four sections: Populated, For the owner (open `what`
questions with their defaults, and challenges), Decided without the owner (the digest the owner can
reclaim from), Spikes recorded.

**Recording.** Every commit that changes a file under the tree root carries exactly one
`Node-Change` trailer: `usage` by default (new nodes, and revisions driven by an owner's answer, a
finished spike or use), `rework` for a revision of a node an earlier expert pass wrote wrongly,
never `owner`.

**Not built yet.** Launching the expert from a label or from the planner; running the spikes it
records. The question session (§4.10) and the mechanical hold of a pull request that touches a goal
or an evaluator now exist; the expert's own constraint is still its prompt.

### 4.10 Question sessions and the guard on the what (`agent-os-sessions`)

Stage 1 of `docs/AGENTOS_V2_PLAN.md`; code in `agent_os/product/sessions/`
(`docs/tree/dec-a-question-session-is-a-github-issue.md`,
`docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`).

**The expert's summary is not parsed.** The expert's "For the owner" section (§4.9) is a view of
what is already in the tree: every open `what` question is an `experiments` entry of its node, and
that is what `open` reads, so the session issue is built from the tree and never from a comment. Its
"Decided without the owner" section is different: the digest of a session comes from the judgments
log, so the expert records each such line as a judgment (`prompts/expert.md`) and it reaches the
owner through the next session issue.

**The judgments log.** What an agent decided alone is recorded so that a question session can show
the owner what was decided without them, and so that how often such decisions are undone can be
measured per role and kind. Two append-only files under `.cache/judgments/`, joined by
`judgment_id` and written with `agent_os.product.records` (so each record is stamped with the model,
the CLI version and the method version):

- `judgments.jsonl`: `schema`, `judgment_id`, `recorded_at`, `role`, `kind` (free: the sort of
  decision), `node` (a node id or null), `decision` (one line), `scope` (`what`: it was the owner's
  and they were not asked; `how`: the agents' own call), `versions`.
- `outcomes.jsonl`: `schema`, `judgment_id`, `recorded_at`, `outcome` (`confirmed`, `reversed` or
  `reclaimed`), `source`, `detail`. An outcome for a judgment nobody recorded is refused.

Written with `agent-os-sessions judgment ...` and `agent-os-sessions outcome ...`.

**A question session.** The owner asks (`agent-os-sessions open`; `--dry-run` prints the body):
ONE issue is created, labelled `status:blocked-on-human`, so the owner's reply wakes the planner
through the mechanism v1 already has (§2.1, the guard's reply check). It freezes the batch: every
open question of `what` of the tree numbered, grouped by branch (the goal at the root of its
chain), ordered by what each blocks (nodes below it and nodes depending on it), each with the
default that stands meanwhile; every challenge; and a digest of the judgments recorded since the
previous session (the latest 20; `.cache/sessions/sessions.jsonl` remembers when that was). A hidden
JSON block carries the frozen numbers, so the reply is parsed against the batch as it was shown.
With nothing waiting no issue is opened.

**The reply.** `1: yes; 3: no, rather <answer>` -- `yes` accepts the default, `no, rather X` (or
`no: X`) answers X, any other text after the number is the answer, a bare `no` declines the default
without an answer and the question stays open, and `reclaim M` takes digest entry M back
(`docs/adr/2026-10-07-the-reply-to-a-question-session-is-a-short-numbered-list.md`). Only comments
of `project.human_login` count; a later answer to a number replaces an earlier one. A question left
unanswered keeps its default, stays `open` and is in the next session's batch.
`agent-os-sessions answers N` shows what was parsed.

**Write-back.** `agent-os-sessions apply N` writes each answer into its node (the question becomes
`answered`, the owner's words exactly its `finding`) and each reclaim as a new open question of
`what` on the judgment's node, whose default is the reclaimed decision, and records a `reclaimed`
outcome against the judgment. It edits the working tree only: the planner has a worker commit it
on a branch and open a pull request whose body carries `Session-Answer: #N`. The frontmatter is
re-dumped, so comments inside it are not kept.

**The guard.** `agent-os-sessions guard-what PR` exits 1 and prints one line per file when the pull
request changes (either side of the diff, renames included) a goal node or a path of
`tree.owner_only_paths` -- the other evaluators: the method battery, the thresholds of its
indicators, the rule that tells what from how -- or a file under the tree root it cannot read. Such
a pull request is never merged automatically: it is condition 6 of the control plane's merge gate
(§2.4). `agent-os-sessions verify-answer PR --session N` is what the validator runs on a pull
request claiming `Session-Answer: #N`: exit 0 only when every changed file is a node whose sole
difference is an answer (or reclaimed question) the owner gave, word for word.

### 4.11 The test session of the owner, ingested (`agent-os-sessions test-ingest`)

The owner tries what changed inside the running product and closes the session there
(`docs/tree/uc-open-a-test-session-for-a-branch.md`, `docs/tree/dec-a-test-session-happens-inside-the-app.md`).
**The app writes the result and never touches the tree**; carrying it there is Agentos'. What every v2
product writes when a session closes is the **contract**: `<tree.test_sessions_dir>/<id>.json`, one JSON
object, written whole each time, id `ts-<YYYYMMDD>-<HHMMSS>-<6 hex>`.

| key | content |
|---|---|
| `schema` | optional integer, the version of this contract; absent means 1, the one described here. The reader has one parser per schema and **names and skips a closed session written in a schema it does not read** (exit 1, the session stays pending); an open one is ignored whatever its schema |
| `id`, `branch`, `branch_title` | the session and the requirement of the tree it tests |
| `status`, `opened_at`, `closed_at` | `open` or `closed`; ISO-8601 moments **with a UTC offset** (a moment without one cannot be placed against the feedback log) |
| `commit`, `since`, `changes`, `changes_problem` | where the repository stood when it opened, the previous session of the branch, and what changed; ingestion does not read them |
| `cases` | `[{node, title, state, verdict, note}]`, `verdict` one of `accept`, `reject`, `not_tried` |
| `questions` | `[{node, question, default_answer, date, answer}]`; `answer` is `null` when the owner did not answer, and then the default stands |

**The command** reads the closed sessions not yet ingested and, by default, **prints the plan and writes
nothing**; `--apply` carries it out; `--session ID` plans or applies one session again; `--sessions-dir` and
`--root` override the keys. A file that breaks the contract is named on stderr and skipped (exit 1 at the end);
a missing directory is refused naming `tree.test_sessions_dir`. Per session:

- an **answered question** is written into its node, the owner's words exactly (the same edit as
  `agent-os-sessions apply`); an unanswered one is left alone and **its default stands**, which the plan says;
- a **rejected case** becomes one rework issue for its node: the seven sections of a brief (validated before
  anything is written), `type:bug` plus `tree.ticket_labels`, `<!-- node: -->`, the budget class
  `tree.ticket_budget_class`, the owner's note quoted whole and the session id as source, and a
  `<!-- key: test-rework.<session>.<node> -->` line by which a second run finds the issue it already opened. No
  `status:*` label is set (as `compile` does not): moving it to `ready` is the planner's or the owner's step.
  Whether a note asks to *fix* or to *decide* is not reliably readable from free text, so every rejection is
  rework and the ticket tells the worker to record a question of what instead when the note asks to decide; the
  expert may reclassify it;
- an **accepted case** is recorded on its node as `acceptances: [{session, date}]`, once per session;
- a case **not tried** is left alone;
- the **verdicts on improvised answers** that `feedback.jsonl` holds inside the session's window
  (`opened_at`..`closed_at`: the two files have no other join) are summarised per action and node (accepted,
  rejected with the note, retried) inside the plan, as input; nothing is written from them yet.

A step already done is shown as such and not repeated; a step that cannot be done (a node the tree lacks, a
question the node does not carry open, or already answered with other words) is a `problem:` line, exit 1, and the
session stays pending. The registry of ingested sessions is `.cache/test-sessions/ingested.jsonl`: every effect is
idempotent on its own, so losing it costs a longer plan and no duplicate.

**Hand-off.** The tree edits stay in the working tree, as with `apply`: a worker commits them with
`Node-Change: usage` (revisions driven by the owner's answer or use; never `owner`, which an agent does not
write) and opens a pull request whose body says `Test-Session: <id>`. It changes the what, so it is merged on the
owner's word, which the answers are (`docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`).
The decision: `docs/adr/2026-10-09-a-closed-test-session-is-ingested-by-a-command-that-plans-first.md`.

## 5. Export recipe

1. **Copy `agent_os/` as a unit** — `git subtree add --prefix=agent_os <the split repo> main`,
   or a plain copy for a first look — plus the three files of §4.1 that live outside it, and run
   `bash agent_os/bootstrap.sh`. Nothing under `agent_os/` is edited per project: a host extends
   it through `config/agents.yaml`, through host-owned files that config names, and through hook
   commands
   (`agent_os/docs/adr/2026-09-21-the-mechanism-is-one-directory-extended-by-hosts-and-never-modified.md`).
   The old shape of this step — copy a list of files out of the host's `scripts/` and `tests/` —
   is what #508 replaced. Nothing has to be deleted on the way out any more: the
   Azure DevOps migration block `agent_os.issues` used to carry — its REST helpers and its
   `.git-credentials` reader — was deleted outright once the host project's one migration was
   done, and `git log` keeps it (#364, was gap §7i).
2. **Write the new project's `config/agents.yaml`** — *config only*: start from
   `agent_os/config.example.yaml`, which carries every key of §4.2 filled in for an invented
   project, and copy the
   `project:`/`mechanism:`/`planner:` structure and fill in every key in §4.2; `classes:` can be
   copied as a starting point and tuned later.
3. **Set `project.forbidden_paths` and `project.worker_environment`** in that new
   `config/agents.yaml`: the globs no agent may write — ONE list, behind both the regex `collect`
   audits a run's changed paths with and the "FILES YOU MUST NOT TOUCH" paragraph — and the
   variables exported into a worker's backend process, whose KEYS render the environment paragraph
   as names and never as values. Leave either empty and the driver renders no such paragraph, and
   the audit reports "nothing forbidden" instead of matching every path — **config only** (was gap
   §7a, fixed by #363). Since #509 there is a fourth **config only** half to this step:
   `project.prompt_extras`, one host-owned file per role appended at that role's
   `__PROJECT_EXTRAS__` point — the "RUNNING PYTHON AND TESTS" paragraph that used to be a literal
   in the mechanism's own worker prompt is `config/agent_prompts/worker.md` here, and a host that
   names no file renders nothing there (was gap §7t; §7aa is what a non-Python host still has to
   read past).
   `project.forbidden_paths` is the FIRST of two lists, and the second is not this step's to fill
   in: `mechanism.own_paths` names the machinery's own files, is copied unchanged because it
   travels with the mechanism, and is conditional where the host's is not — a worker's diff may
   touch one of its paths when the issue body names it as the target of the work (§7u,
   `agent_os/docs/adr/2026-09-16-the-mechanisms-own-files-are-not-the-host-projects-protected-paths.md`).
   Never move a host path into it: that would turn an unconditional protection into one a brief
   can lift.
4. **Set `project.never_run`** to whatever this project's agents must never run, each command with
   the one-line reason its prohibition rests on: the worker's, the validator's and the refiner's
   RULES render that one list, so the reason travels with the command and the three copies cannot
   drift — **config only** (was gap §7b, fixed by #363). The refiner's staging rule still names this
   project's own worker classes, the one literal no key feeds in `agent_task.sh` (gap §7t).
5. **Set `project.modules`** to the new project's module names, one per `docs/modules/*.md`:
   they become the `module:<name>` labels `issues.py` creates on the tracker — **config only**
   (was gap §7c, fixed by #364). An empty list simply creates no `module:` label.
6. **Create in GitHub**: the fixed labels (§4.3 — most autocreate on first `move`, three do not);
   a Project v2 with a `Status` field and the six columns; one GitHub App per identity, installed,
   with `.json`+`.pem` under `secrets_dir` — GitHub UI steps `agent-os-doctor` (#511) reads back
   afterwards, one line per check, rather than a step to trust once and forget. The issue templates
   are no longer a separate copy-by-hand step: `agent-os-install` (below) does it.
7. **Create on the machine** (§4.4): `secrets_dir/ntfy_topic`; the root `.env` — still by hand,
   nothing in the mechanism creates a credential. Everything else here is now `agent-os-install
   [--dry-run] [--force]` and `agent_os/bin/worker_task.sh <backend> init` (#511, was gaps §7h and
   §7r): the two worktrees (`init`, idempotent, one call per backend); the systemd units, from
   `agent_os/templates/systemd/*.tmpl` and `project.guard_unit`/`project.executables`, never
   overwritten without `--force` and never armed (`systemctl --user enable --now` stays §6's own
   human step, below); `.claude/agents/{control-plane,task-writer,worker-runner}.md` rendered from
   `agent_os/agents/*.md` (#510) if that directory exists yet; `.github/ISSUE_TEMPLATE/{task,bug}.md`
   and `.github/workflows/ci-agent-os.yml`, copied as-is if absent, plus `.github/workflows/ci-host.yml`
   running `project.test_command` on every pull request. `--dry-run` prints every path
   this would touch and its diff against what is there, so adopting the mechanism on a second
   machine — or checking a first one is still what `config/agents.yaml` describes — is three
   commands instead of a checklist of hand edits.

**Verify without spending money.** `bash agent_os/bin/agent_task.sh validator 1 --dry-run` and
`... refiner 1 --dry-run` resolve class/identity/prompt without calling the backend or minting a
token. Put a stub `claude`/`qwen` first on `PATH` (echo argv, emit one
`{"type":"result","num_turns":3,"total_cost_usd":0.07}` line) the same way
`agent_os/tests/test_worker_task.py` does, and a stub `gh` the same way its fixtures do — there is no single
documented lever for the backend stub the way `AGENT_CLAUDE_BIN`/`PLANNER_CLAUDE_BIN` exist for the
other two drivers (gap, §7f). Run `pytest agent_os/tests/test_agent_guard.py agent_os/tests/test_agent_lib.py
agent_os/tests/test_agent_task.py agent_os/tests/test_issues_cli.py agent_os/tests/test_worker_task.py -q` — the same `not db`
subset CI runs, no Postgres required. `agent_guard.py tick` with `WORKER_CACHE_DIR` pointed at a
temporary directory exercises the driver and the guard in isolation together: the guard's own
`cache_dir()` reads the same variable (#377), so its worker state, `planner_events/` and
`planner.lock` all land in that directory and the real `.cache/` — shared with every worktree of the
checkout by symlink — is left alone. `agent_os/tests/test_agent_guard.py` runs `check` that way and asserts
it (#360).

## 6. Operating it: the first real run

Adopting the mechanism on a machine is three commands: `agent-os-install [--dry-run] [--force]`
(§4.4, §5 step 7) for the systemd units and the copy-if-absent templates; `agent_os/bin/worker_task.sh
<backend> init` per backend for the worktree; `agent-os-doctor` (§4.4) to read the whole first-run
checklist back in one pass and exit 1 on whatever is still missing, rather than trusting the GitHub
UI steps of §4.3 were all actually done. None of the three arms anything — the guard timer's
`systemctl --user enable --now` is still the one command in this section that stays a human's own
call (#511, was gaps §7h and §7r).

Before moving any issue to `status:ready` for the first time: create the three labels that
never autocreate (`status:agents-paused`, `auto-ready`, `wake:planner` — `status:ai-completed`, like
every state label, autocreates on its first real use); make sure every issue meant for the trial is actually a Project item with a
`Status` value set (an item can exist with no Status, or not exist on the board at all); make sure
each worker's worktree is on a fresh branch, not a stale one left over from a previous batch of
work; and decide by hand what to do with any issue stuck in `status:refine` whose parent carries no
`auto-ready` (there is no mechanical way out of that state — a human moves it or labels the parent).

Watch the first run closely rather than trusting the configuration alone:
`worker_task.sh <backend> watch` (tail the event stream), `journalctl --user -u
<guard>.service -f` (tick output), and `.cache/<role>/runs.tsv` (cost as it accrues). In the host
project this document was written for, the mechanism has never dispatched a real worker: the guard
timer ticks every five minutes and finds nothing dispatchable, the planner has zero recorded runs
since the timer was last armed, and no comment, commit or PR anywhere carries a bot identity's
signature — the wiring (Apps installed, secrets present, permissions correct) is complete but
untested end to end. The first real dispatch is the first time any of it is exercised under load.

## 7. Known gaps, ordered

| Gap | Evidence | Consequence | Proposed fix | Size |
|---|---|---|---|---|
| (a) **Fixed (#363).** Host-project literals in the worker's injected prompt: the forbidden-path list and the DB sentence are config now, not script text. `project.forbidden_paths` is ONE list behind both halves of its own rule — the regex `collect` audits a run's changed paths with, and the "FILES YOU MUST NOT TOUCH" paragraph (the ownership rule has a second list with a second such pair since #390, row (u)) — and the sentence that spelled the Postgres port became a paragraph rendered from `project.worker_environment`'s KEYS (names, never values) that disappears when the mapping is empty | `project.forbidden_paths`/`project.worker_environment` in `config/agents.yaml`; `agent_lib.forbidden_paths_regex`, `forbidden_paths_rules`, `worker_environment_rules`; `__FORBIDDEN_PATHS_RULES__`/`__WORKER_ENVIRONMENT_RULES__` in `agent_os/bin/worker_task.sh` | (resolved) | (resolved) | S |
| (b) **Fixed (#363).** The host domain's pipeline verbs were spelled three times, once per RULES block (worker, validator, refiner); all three render the same `project.never_run` list now, each command with the one-line reason its prohibition rests on, and an empty list renders no such paragraph anywhere | `project.never_run` in `config/agents.yaml`; `agent_lib.never_run_rules`; `__NEVER_RUN_RULES__` in `agent_os/bin/worker_task.sh` and in both `agent_os/bin/agent_task.sh` blocks | (resolved) | (resolved) | S |
| (c) **Fixed (#364).** The 15 module labels were a list in `issues.py`; they are `project.modules` now, and `fixed_labels()` builds the `module:<name>` half of the fixed label set from it, so a second project writes its own names in config and changes no code | `project.modules` in `config/agents.yaml`; `agent_lib.ProjectConfig.modules`; `issues.fixed_labels` | (resolved) | (resolved) | S |
| (d) **Fixed (#364).** `project.repo` was declared and never read. `repo_name()` resolves three steps now — the `AGENT_OS_GH_REPO` env variable, which names no project where `ROEDOR_GH_REPO` did; then `project.repo`; then `gh repo view` on the cwd — so a command run from outside the clone reaches the configured tracker instead of whatever the cwd happens to be | `issues.repo_name`; `project.repo`'s comment in `config/agents.yaml`, which used to document its own drift | (resolved) | (resolved) | S |
| (e) **Fixed (#377).** `agent_guard.py`'s `worker_paths()` ignored `WORKER_CACHE_DIR` while `worker_task.sh` honoured it, so a test or dry-run that isolated the driver still left the guard reading/writing the real `.cache/` and the two could disagree about what run exists. One `cache_dir()` reads the override now, and every path the guard derives comes from it: the worker files, `planner_events/`, the planner's run directory and `wake`'s `planner.lock` | `agent_os.guard`: `cache_dir()` and its callers `worker_paths()`, `events_dir()`, `planner_dir()`, `wake`'s `lock_path`; `agent_os/bin/worker_task.sh`'s `cache=` reads the same variable; `agent_os/tests/test_agent_guard.py` pins both halves — the override's four paths and a real `check` subprocess against the untouched `.cache/` (#360) | (resolved) | (resolved) | S |
| (f) **Fixed (#380).** `worker_task.sh` called `qwen`/`claude` by bare name while the other two drivers had a binary-indirection variable, so which binary a dispatch ran depended on the PATH of whatever launched the driver — and the systemd user manager's PATH does not carry nvm, which is why the first unattended dispatch died in under a second. All three drivers now resolve the command through `agent_lib backend-executable`, from `project.executables` keyed by command name, falling back to the bare name a project that configures none. The mapping ships EMPTY on purpose: a configured absolute path outranks the `PATH` stub every driver test protects itself with, so filling it in goes together with an `AGENTS_CONFIG_PATH` override in those fixtures | `project.executables` in `config/agents.yaml`; `agent_lib.ProjectConfig.executables`/`backend_executable`; `WORKER_BACKEND_BIN` in `agent_os/bin/worker_task.sh`, `agent_executable` in `agent_os/bin/agent_task.sh` and `agent_os/bin/planner_task.sh` | (resolved) | (resolved) | S |
| (g) **Fixed (#366).** The quota-exhaustion page was a Spanish literal in `agent_guard.py`, so the one channel that reaches the human's phone was the one place `project.human_language` could not reach. Every page is a one-line template under `project.messages` now, rendered by `agent_lib.render_human_message`, which fails loudly on a key the project never wrote and on a placeholder nobody passed; a test parses both `agent_guard.py` and `issues.py` and refuses any literal reaching `notify.sh`. A template `str.format` cannot parse is refused when the config loads rather than on the page, and no page ever fails the state change it announces: the cut, the cap and the label are already written, so an unrenderable or unsendable page is printed and the run carries on instead of aborting the tick and the other backend's check with it. The English operational line a run prints to its journal is deliberately a separate string: different reader | `project.messages` in `config/agents.yaml`; `agent_lib.render_human_message`; the ADR's 2026-09-16 amendment | (resolved) | (resolved) | S |
| (h) **Fixed (#511, PATH closed 2026-09-22).** The ADR promised an `install` subcommand generating the systemd units from `project:`; `agent-os-install [--dry-run] [--force]` now renders `agent_os/templates/systemd/{guard.service,guard.timer,override.conf}.tmpl` from `project.guard_unit` and `project.executables`, writes `~/.config/systemd/user/<guard_unit>.{service,timer}` and `.service.d/override.conf`, and never overwrites an existing file without `--force`; `--dry-run` prints every path and its diff. Verified on roedor: `WorkingDirectory=`/`ExecStart=`/`KillMode=process` match the units armed by hand exactly. Since #51 `ExecStart=` deliberately no longer matches in one respect: the hand-armed unit ran the shim on the host's root `.venv`, and the generated one runs it on the mechanism's own interpreter (§8). `Environment=PATH=` was left as the one open gap when #511 merged, because `project.executables` was empty (row (f)'s test-isolation tradeoff, made moot the same day by #512: the mechanism's own suite now always loads `agent_os/config.example.yaml`, never this file, so a value here cannot reach a driver test's fake backend). Filled in the same day with `qwen`, `claude` and `gh`'s absolute paths (`gh` is not a worker backend, but it is the only other bare-name command the tick calls dozens of times per run and the only hook `project.executables` gives for adding a directory to the generated `PATH`) — the generated unit's `PATH` now matches the hand-armed one on every directory that resolves to something (confirmed empty: `/home/linuxbrew/.linuxbrew/sbin`, present in the old hand-armed `PATH` but nothing lives under it). The hand-written `roedor-guard.service.d/10-worker-survival.conf` this closed is removed — keeping it next to the now-equivalent generated `override.conf` would have been two sources of truth for the same `PATH`/`KillMode`, with `override.conf` silently winning (`o` sorts after `1`) and no test watching either. The three unit files were written through `agent_os.install.plan_systemd_units` directly — the same rendering `agent-os-install --force` uses, but not `--force` itself, which in the same pass also rewrites `.claude/agents/*.md` and adds the CI snippet — then `daemon-reload`d; `agent-os-install --dry-run` reports the three as `exists, up to date`, while the host's `.claude/agents/*.md` copies are still the pre-#510 ones and remain a pending step of their own. `install` never enables, restarts or reloads a unit itself: arming stays `docs/runbooks/agent_monitor.md`'s own human step, and the timer was already armed so this needed no re-arm, only the reload | `agent_os/agent_os/install.py`; `agent_os/templates/systemd/*.tmpl`; `agent_os/tests/test_install.py`; `config/agents.yaml`'s `project.executables`; `docs/runbooks/agent_monitor.md` | (resolved) | (resolved) | S |
| (i) **Fixed (#364).** The Azure DevOps migration block (org, project, `.git-credentials` read in the clear, the HTML↔markdown converter pair only it used) is deleted, along with the `migrate-ado` subcommand and its tests; the host project's one migration ran on 2026-09-13 and `git log` keeps the code that ran it. `flatten` and `validate`, which the `load` subcommand shares, stayed | `agent_os.issues` (no `migrate-ado`); `agent_os/tests/test_issues_cli.py` | (resolved) | (resolved) | S |
| (j) **Fixed (#365).** `promote-refined` was never called from `tick`; only the planner's prompt invoked it, on `refiner_finished`. `tick` calls `promote_refined()` on every fire now (it is idempotent and already tested) and the planner's rules no longer name it — a promoted issue reaches the planner as a `new_dispatchable` event instead, so the promotion no longer depends on an LLM remembering a step | `agent_os.guard` `tick`; `agent_os/bin/planner_task.sh`'s `refiner_finished` paragraph; predicate `agent_lib.promotable_to_ready` | (resolved) | (resolved) | S |
| (k) **Fixed (#374).** The one-module-per-backend exclusion existed only as prompt text (the relaunch cap half of this row moved into code in #362: `worker_task.sh resume` itself refuses past `planner.relaunch_cap`); it and a new configured parallelism cap (`planner.max_parallel_issues`, default 1) now both live in `worker_task.sh start`, which refuses, writing nothing, before an over-cap or same-module dispatch | `agent_os/bin/worker_task.sh` `start`; `planner.max_parallel_issues` in `config/agents.yaml`; agent_os/docs/adr/2026-09-15-parallelism-is-a-configured-cap-enforced-by-the-driver.md | (resolved) | (resolved) | S |
| (l) **Fixed (#365).** A native GitHub close-by-merge never updated `status:*` or the board column. The tick now reconciles it: every closed issue still carrying a state label is moved through `issues.py move N done` — the same path a human's move takes, so the label vocabulary and the board mirroring have one implementation — and each reconciliation is logged with its issue number | Observed on #348, #349, #357 (closed, still `status:review` on both label and board) — GitHub's own auto-close on `Closes #N` never calls `issues.py move N done`. `agent_os.guard` `closed_issues_with_status_label`/`reconcile_closed_issues` | (resolved) | (resolved) | S |
| (m) **Fixed (#366).** There is a third ntfy trigger: `issues.py move N review` pages `review_ready` after the label and the board column are written, once per issue — the marker under `.cache/paged-review/` is *claimed* with an exclusive create, so two concurrent moves cannot both pass an `exists()` check and both page — and a page that fails never fails the move and releases the claim, so the next one may still try | `issues.page_review_ready`; `project.messages.review_ready`; the ADR's 2026-09-16 amendment (#366); §2.1 row 5 | (resolved) | (resolved) | S |
| (n) **Partly fixed (#387).** No HUMAN-VISIBLE aggregate view of spend per feature, or per issue in dollars: the per-issue TOKEN total is now printed by `worker_task.sh <backend> status`/`collect` beside its ceiling and by the stage gate's cut message, but the dollar sum still only exists as an input to the guard's own check and per-feature summing still does not exist at all | see §3 — `cumulative_total_tokens` printed via `worker_task.sh` `issue_token_line`; `cumulative_cost_usd` (#375) unprinted, and `0.0000` on every Qwen issue | A 10x overrun on one issue is now visible in tokens while it runs, but nothing answers "what did this feature cost" and no figure reaches GitHub | #367: a report script over `cumulative_total_tokens` plus a per-feature join via `gh issue view --json parent` — reading tokens, or it prints 0.00 USD for everything | M |
| (o) **Fixed (#365).** An orphan `status:doing` issue (no live worker running it, not blocked on a human) was only ever logged. It writes an `orphan_doing` event now, at most one per issue per `planner.idle_wake_minutes`, and the planner's rules carry a paragraph for it: back to `status:ready` when the branch is clean and the relaunch cap allows another try, a question for the human otherwise. `_log_state_drift` is unchanged and still LOG ONLY — drift between the `.state` marker and the label is a thing to notice, an orphan is a thing to act on | `agent_os.guard` `orphan_doing_issues`, `_write_orphan_doing_events_if_due`, `_issues_a_live_worker_is_running`; `agent_os/bin/planner_task.sh` | (resolved) | (resolved) | S |
| (p) The validator and the refiner sign as the planner's own App, not their own | `config/agents.yaml:61` (`role_apps: {}`), resolved in `agent_os.lib:246-252` | GitHub history can't distinguish which role posted a given comment/label change — the same problem the planner's own identity ADR solved for the planner, unresolved for these two | create `roedor-validator`/`roedor-refiner` Apps (a browser step) and set `role_apps` | S (per role, browser step) |
| (q) Budget classes are placeholders, never calibrated against real runs — though three issues are now measured in tokens: #363 49,526,715 (ten stage logs, four of them counting 0), #390 14,405,623 (four), #387 14,265,855 (four of five), which is what the five `max_total_tokens` values rest on | `config/agents.yaml:6-7` names this explicitly and #342 owns it; the comment above `classes:` records the measurement and the fact that the numbers are placeholders | A ceiling set without calibration cuts either too early (a healthy task dies mid-stage, and a cap that cuts good work gets disabled, which is worse than none) or too late (it only ever catches the runaway) | #342: tune `max_context`/`max_cost_usd`/`max_total_tokens` from the recorded `.jsonl`, per class, now that `cumulative-tokens` makes one issue's total a single command | M |
| (r) **Fixed (#511, was half-fixed by #392).** Worktrees were created by hand; `agent_os/bin/worker_task.sh <backend> init` now does it — idempotent (`[ -e "$worktree/.git" ]`, the same test `worker_task.sh` itself refuses on, leaves an existing worktree exactly alone), `git worktree add` on a fresh branch (`agent-os/init-<backend>`) from `origin/main` -- or on that same branch, moved to the tip of `origin/main`, when it survived a worktree that did not and holds no commit `origin/main` lacks (stage 1f: a lost worktree is recreated instead of dying on "a branch named ... already exists"; a branch with commits of its own, or one checked out in another worktree, is refused with the commands to keep or drop it) -- plus a `.venv`/`.env` symlink from the host root when either is missing so the worktree can run a test and reach a credential the first time it starts. It still does not undo what merging with `gh pr merge --delete-branch` deletes — `init` is the recovery, not a guard against the deletion — but "adopt a new backend" and "recover after a stale branch was deleted with its PR" are now one command instead of a hand-run `git worktree add` nobody had written down the flags for. `dispatchable_scan`'s exclusion and the missing-worktree page from #392 are unchanged | `agent_os/bin/worker_task.sh`'s `init` case and `agent_os/bin/worker_init_worktree.sh`; `agent_os/tests/test_worker_task.py`'s and `tests/product/worker/`'s `init` tests | (resolved) | (resolved) | S |
| (s) **Fixed (#363).** `docs/modules/workers.md`'s Contract listed the forbidden paths in prose and omitted four the regex actually protected; it points at the configured keys instead of restating either list now — the two of them since #390, row (u) — naming the functions that derive each half's audit regex and injected paragraph from it, so the doc cannot drift from the rule again | `docs/modules/workers.md`'s own "File ownership" paragraph; `project.forbidden_paths` and `mechanism.own_paths` in `config/agents.yaml` | (resolved) | (resolved) | S |
| (t) **Fixed (#509).** Two host literals remained inside the injected prompts, in text no `project:` key fed: the worker's "RUNNING PYTHON AND TESTS" paragraph named this project's importable package and its DB fixture, and the refiner's staging rule named this project's own worker classes. Every role's prompt is a template file now — `agent_os/prompts/{worker,validator,refiner,planner}.md`, one per role, none of them inside a driver — rendered by one function, `agent_lib.render_prompt`, with a single marked extension point, `__PROJECT_EXTRAS__`, where the host's own text is appended from the file `project.prompt_extras` names for that role. roedor's two paragraphs are `config/agent_prompts/worker.md` and `config/agent_prompts/refiner.md`, and the mechanism renders them exactly where it used to spell them, so nothing an agent reads moved. The renderer refuses an extras file the config names and the filesystem lacks, and any placeholder nothing answered, because either one reaches an agent as a clause it cannot act on | `agent_os/prompts/`, `agent_lib.render_prompt`/`prompt_substitutions`/`prompt_extras_path`, `project.prompt_extras` in `config/agents.yaml`; `agent_os/tests/golden/<role>.md` captured by `agent_os/tests/capture_golden.sh` before the move and compared after it by `agent_os/tests/test_prompt_templates.py`, which is what proves the four prompts render word for word what they rendered before | (resolved) | (resolved) | S |
| (aa) **Fixed (agent-os#41).** The validator's prompt named `.venv` twice — the lint command (`.venv/bin/ruff check <files>`) and the warning against linking the checkout's `.venv` into a worktree — and claimed a worktree only a root `.venv` host gets was "already populated". The lint bullet is `__LINT_RULES__` from `project.lint_commands`, the warning names no layout, and the worktree is provisioned from `project.worktree_links`/`project.worktree_setup_command` | `agent_lib.lint_rules`; `agent_provision_worktree` in `agent_os/bin/agent_task.sh`; `LITERALS_A_TEMPLATE_STILL_CARRIES` is empty | (resolved) | (resolved) | S |
| (ab) **Fixed (agent-os#86).** A dirty worker worktree deadlocked its backend with nobody told: `start`, `resume` and `branch` refused over it, the planner read the refusal as "wait for the next event", and no event ever cleans a worktree. Most of the dirt was the run's own `scratchpad/`, which each run state had needed its own exemption for (#18, #22, #75, #84). The driver now writes `scratchpad/.gitignore` containing `*` in every worker worktree it touches (`hide_scratchpad_from_git`, before every dirty check and before the cut's freeze, which therefore no longer sweeps scratch into the WIP commit); the #75 archive still empties it for each new run. What is still dirt is read by the guard on every tick (`backend_worktree_dirt`): the backend's ready issues leave the dispatchable set (`DispatchableScan.dirty_worktree`) and the human is paged once per listing (`backend_worktree_dirty`) | `agent_os/bin/worker_task.sh`; `agent_os/guard.py`; `docs/adr/2026-09-25-scratch-is-invisible-to-git-and-a-dirty-idle-worktree-is-paged-by-the-guard.md` | (resolved) | (resolved) | S |
| (u) **Fixed (#390).** The ownership rule's one list mixed two things that are not alike: the host project's protected paths, which hold whatever a brief says, and the mechanism's own files, which the tracking epic exists to change — so #363 went out with a body naming `agent_os/bin/worker_task.sh` in four of six acceptance criteria, the worker wrote it correctly, and the result then failed the merge gate on the very rule the same driver injects (#386; #388 and #389 were in the same position). Two configured keys now, one rule each: `project.forbidden_paths` stays unconditional and a brief naming one of its paths is a defect in the brief, while `mechanism.own_paths` — its own top-level section, because it travels with the mechanism and is not the host's to configure — yields to an issue body that names the path, matched as a literal substring of the `.body.md` the run already fetched and asked only for the paths the second regex matched. Both halves of each rule render from their own key (`FORBIDDEN`/`MECHANISM` for the audit, the two RULES paragraphs for the prompt), the pair of paragraphs renders whole or not at all, and a path on both lists stays refused by the host half whatever the body says. Editing a driver from a worktree cannot break the run in progress, which executes the main checkout's copy; the rule that protects the run is the one forbidding writes there at all | `mechanism.own_paths` in `config/agents.yaml`; `agent_lib.MechanismConfig`/`load_mechanism`, `mechanism_paths_regex`, `mechanism_paths_rules`; `MECHANISM`, `issue_body_names_path` and `__MECHANISM_PATHS_RULES__` in `agent_os/bin/worker_task.sh`; `agent_os/docs/adr/2026-09-16-the-mechanisms-own-files-are-not-the-host-projects-protected-paths.md` | (resolved) | (resolved) | S |
| (x2) **Fixed (agent-os#61).** `open-pr` read every rejected push as a remote branch with commits the worktree lacked, tried a fetch plus `--ff-only`, wrote `BLOCKED reason=push_rejected` and exited 1 — leaving finished work in `status:doing` with no pull request, no comment and no `blocked-on-human`. A worker App without the Workflows permission is refused a new ref whose tree differs from the default branch under `.github/workflows/`, and a stale branch (the one the conflict path pushes unmerged) differs that way without touching a workflow. The rejection is now classified: that refusal writes `BLOCKED reason=workflows_permission`, skips the fast-forward attempt, and comments GitHub's words plus what unblocks it (merge the base, push, `open-pr` again — or grant `workflows: write`); any other rejection keeps `push_rejected` and the fast-forward attempt. Either way the issue gets the comment and `status:blocked-on-human`. A later successful `open-pr` rewrites a leftover `BLOCKED` line 1 of `.state` to `DONE` | the `open-pr` case in `agent_os/bin/worker_task.sh` | (resolved) | (resolved) | S |
| (x) **Fixed (#389).** A pull request the mechanism opened in conflict with its base carried **zero** check runs, not failing ones: GitHub creates `refs/pull/N/merge` only for a mergeable pull request, an `on: pull_request` workflow checks out exactly that ref, so no merge ref means no workflow run at all — and a pull request with no checks can never meet the merge conditions. PR #386 (2026-09-16) had 0 runs and only `/head` on the remote; merging `origin/main` into the branch and pushing produced the merge ref and CI started within seconds. `open-pr` now fetches the base and merges it before pushing, committing a clean merge with a subject naming the base and the commit; a merge that conflicts is aborted (worktree untouched), the branch is pushed and the pull request opened anyway — one that exists and says why it is red beats finished work with no pull request — and the issue gets a comment naming the conflicting paths plus `status:blocked-on-human` instead of `status:ai-completed`. After `gh pr create` the PR's own `mergeable` is read back and printed; `CONFLICTING` takes the same route, `UNKNOWN` (GitHub computes it asynchronously) is printed as the real answer it is. Skipped entirely when `open-pr` was going to refuse anyway | the `open-pr` case in `agent_os/bin/worker_task.sh`; `.github/workflows/ci.yml` (`on: pull_request`, no filters) | (resolved) | (resolved) | S |
| (w) **Fixed (#388).** Nothing in `start` looked at which branch the worktree was on, so a dispatch inherited whatever the previous issue left behind — after #363 finished, the Qwen worktree stayed on `task/363-prompts-config-literals` and the next dispatch would have written its commits inside that already-open pull request. `start` now refuses, writing nothing, unless HEAD is the issue's own base (`Base: <branch>`, `main` when it names none — one `issue_base_branch` shared with `open-pr` and the stage fork point, where the same sed had been written three times) or a branch whose name carries the issue number. `--force` skips it and says so; `resume` is not subject to it, a resumed run being meant to sit on the branch its own issue created. First of the gates: on the normal path it is a string comparison and costs no `gh` call, while the parallelism cap and the module exclusion after it do | `issue_base_branch` and the `start` gate in `agent_os/bin/worker_task.sh`; agent_os/docs/adr/2026-09-15-parallelism-is-a-configured-cap-enforced-by-the-driver.md (the precedent: a rule the planner is told to follow becomes one the driver enforces) | (resolved) | (resolved) | S |
| (v) Both issue-wide sums count a stage **0** when its own terminal `result` carries no tokens, in two shapes, so the undercount lands exactly on the runaway the ceilings exist to stop | `agent_lib.cumulative_total_tokens` and `agent_guard.tokens_spent_on_issue` state the first shape in their docstrings rather than papering over it. Measured over #363's ten stage logs, four contribute 0: three have no terminal `result` at all (1, 30 and 46 turns of real work, uncounted) and a fourth ends in `subtype=error_during_execution` whose `usage` is `{"input_tokens": 0, "output_tokens": 0}` despite 12 turns — the second shape, which no docstring mentions. Its 49,526,715 is therefore a floor, not a total. Raised by the human on #387 (2026-09-16) and deliberately left outside that issue's scope | An issue that chains cuts, or whose stages die on a backend error, is measured below what it actually spent, so the token ceiling fires later than it should — and repeated relaunches, which is what a runaway looks like, are precisely what produces both shapes | Either count such a log at its per-turn sum, labelled as the upper bound no terminal event corroborates, or have `archive_stage_events` append a terminal marker when it files a stage's log, so the archived record says what that process was made to spend whichever way it ended | M |
| (y) **Fixed (#400).** A one-shot role ran in the FOREGROUND of whoever launched it, so whether a validator survived depended on the planner LLM choosing to wait for a command its own tool had already backgrounded — while the planner's prompt assumed the opposite ("a `validator_finished` event brings you back when it is done"). The driver now prepares the run in the caller's own shell, so the resolution, the identity and any worktree WARNING are read on its stdout, then hands the run to `setsid nohup … </dev/null &`, waits bounded ~2 s for the run's session id to equal its pid, prints `detached:`/`pidfile:`/`log` and exits. The run re-enters the same file with `AGENT_DETACHED_RUN=yes` and NO ARGUMENT (the no-argument half is #475's: the launching half passes none, so an invocation that carries one is a role of its own however stale that variable in its environment happens to be) for everything that follows the backend — the `runs.tsv` row, the `<role>_finished` event, `wake`, the worktree's removal — so there is one implementation and no script body passed to `bash -c`. Its PID file, beside the log of the same stamp and removed as the run's own last step, is what the tick scans into a `role_died` event (§1), and the planner's rules now say the launch returns at once and carry a paragraph for that event | `.cache/planner/20260916T230532Z.log` (PR #399, issue #393) carries both `agent_task.sh validator 399` and the tool's own "did not complete within its 120s timeout"; `.cache/validator/20260916T230556Z.log` ends at 2026-09-16T23:08:05Z with zero `"type":"result"` events, and that run wrote no `runs.tsv` row, no event and no review (the row and the event #399 has today are a hand re-run's, 2026-09-17T01:31:29Z). Code: `agent_detached_run`/`agent_wait_for_own_session` in `agent_os/bin/agent_task.sh`; `role_run_death`/`dead_role_runs`/`_write_role_died_events` in `agent_os.guard`; the `role_died` rules in `agent_os/bin/planner_task.sh`. Tests: `agent_os/tests/test_agent_task.py` kills the launching shell by process group and shows the run finishing anyway; `agent_os/tests/test_agent_guard.py` covers the scan, the two shapes' wording and the paused epic | (resolved) | (resolved) | S |
| (z) Two edges of the detach stay open, both measured rather than assumed | the PID file is written only once `agent_wait_for_own_session` returns, up to ~2 s after the fork (`agent_os/bin/agent_task.sh`), and liveness in the scan is `os.kill(pid, 0)` with no identity check (`agent_guard._is_alive`) | A run killed inside that window leaves no PID file at all, so nothing reports it and the pull request it owed a review looks merely unvalidated instead of dead — the silence #400 exists to end, in a narrower window. A PID recycled inside one tick would read as a live run: `/proc/sys/kernel/pid_max` reads 4194304 here against a five-minute tick, so that is unlikely rather than impossible, and the file goes on the tick that reports it | Leave a marker the scan can read as a launch that never took (the file can exist before the pid is known, and an empty one is that case), or key the scan on the run's own first log line. Closing the reuse half needs an identity check — the run's session id, or its `role:`/`subject:` header against `/proc/<pid>/cmdline` — which #400's criterion does not ask for | S |

## 8. Command reference

Two spellings of every Python command, and they are the same command: `<agent_os python> -m
agent_os.<module> …` is what the drivers run, and `agent-os-<module> …` is the console script a
host that wants one on its PATH gets from `pyproject.toml`. In roedor, `scripts/<old name>` is a
third: the shim (§4.1). The interpreter is the one `agent_os_python()` resolves — never a host's.
That includes the guard unit `agent-os-install` renders: its `ExecStart=` runs the shim, or the
module form on a host without one, on that interpreter even when the host has a root `.venv`, and
install refuses when it resolves to no absolute executable (#12, #51).

| Command | Who uses it | What it does |
|---|---|---|
| `bash agent_os/bootstrap.sh` | human, CI | build `agent_os/.venv` and install the package into it, editable. Idempotent; the one prerequisite of everything below |
| `agent_os/.venv/bin/pytest agent_os/tests -q` | human, CI | the mechanism's own suite: no database, no network, no real backend. The run a second host can also make |
| `agent-os-quality --base REF` | CI | the code-quality ratchet (§4.8): new files and folders must be within the line and entry limits, touched ones never worse than on the merge-base with REF. Exit 0/1/2 |
| `agent_os.issues list/show/create/validate/move` | human, refiner, planner | list/inspect the tracker; scaffold or validate a template-conformant issue; set the one `status:*` label and mirror the board column. `move N [N …] STATE` takes several numbers in one invocation: the target label and the board's `Status` field are resolved once for all of them, an issue that fails is reported under its number without stopping the rest, and the command exits non-zero naming every issue that did not move. A move costs three GraphQL requests of ~1 point each, whatever the board's size (the board field, once per invocation; the issue's item; the column edit) — the issue and its labels are read and written over REST, on the separate core quota (agent-os#27). The GraphQL quota is 5000 points an hour per user, shared by every host and tool the human runs, and separate from the REST `core` one (`gh api rate_limit --jq .resources.graphql`, not the top-level `.rate`). `validate` reads over REST too (agent-os#70). A rate limit is checked against the login's quotas before it is retried: a bucket at zero fails at once, naming it and its reset time; a secondary limit waits at least a minute per retry |
| `agent_os/bin/worker_task.sh <backend> init/branch/start/status/watch/collect/open-pr/stop/resume [--slot N]` | human (direct or via `worker-runner`), planner | `init`: idempotent `git worktree add` on a fresh branch from `origin/main` when the configured path has no worktree yet, then provisioned from `project.worktree_links` and `project.worktree_setup_command` (#511, was gap §7r; agent-os#41). The rest: manage a worker's worktree, branch, dispatch, liveness check, event tail, commit/spend/ownership summary (this stage's context and the issue's token total against both its ceilings), PR, kill, relaunch. On a backend with `slots: N > 1` (#90): `start` and `branch` pick a free slot themselves, `resume --issue <M>` the slot that recorded issue M, `status` and `init` without `--slot` cover every slot, and every other subcommand needs `--slot` |
| `agent-os-install [--dry-run] [--force]` (`agent_os.install`) | human, once per machine | write the systemd `--user` units from `project.guard_unit`/`project.executables` and copy `.claude/agents/*.md` (rendered, if `agent_os/agents/` exists), the issue templates and the CI snippet if absent; never overwrites without `--force`; never enables, restarts or reloads a unit (#511, was gap §7h) |
| `agent-os-doctor` (`agent_os.doctor`) | human, once per machine or after a config change | the first-run checklist of §6 read back mechanically: `gh auth status` scopes, the labels that do not autocreate, the Project v2 `Status` field, each App's secrets, whether the planner's and the validator's Apps may read CI checks, each executable, each worktree, the notify topic file, the guard timer's `is-active`, and (a warning, never a failure) any class a `prompt_extras` file names that `classes:` does not define — one line per check, exit 1 on any failure. Reads state only; never calls `agent_guard.py check` (#511) |
| `agent-os-tree validate\|doctor\|context\|compile\|board` (`agent_os.product.tree`, `agent_os.product.board`) | human, a host's CI, the future planner wiring | the product tree and decision ledger of §4.6: `validate` is the doctor (one line per defect, exit 1), `context NODE` the slice of one node, `compile` the dispatch tickets of the dispatchable nodes (ordered by dependencies, each with its address, dependencies and touched code) and an escalation for each whose mechanism cannot be resolved. Reads files only; creates no issue |
| `agent_os/bin/agent_task.sh expert N [--dry-run]` | human (manual run; never unattended) | one-shot population of the product tree for issue N and one pull request on it (§4.9); detaches like the other one-shot roles |
| `agent-os-sessions judgment\|outcome\|open\|answers\|apply\|guard-what\|verify-answer\|test-ingest` (`agent_os.product.sessions`, `agent_os.product.session_ingest`) | planner, validator, control plane, human | the judgments log, the question session issue and its write-back, and the guard on the what of §4.10: `guard-what PR` exits 1 for a pull request that touches a goal node or an evaluator (merge condition 6), `verify-answer` exits 0 for one that is exactly a session answer. Needs `gh`; never a backend |
| `agent_os/bin/agent_task.sh validator\|refiner N [--dry-run]` | planner, human (manual/`--no-wake` runs) | one-shot review of a PR, or one-shot split/rewrite of an issue, resolving class/identity/prompt without spending when `--dry-run`. The launch DETACHES and returns at once printing the run's pid, PID file and log, so the run outlives whoever launched it and announces its own end as an event (#400) |
| `agent_os/bin/planner_task.sh run ["<context>"]` | guard (`wake`), human (manual) | one `claude -p` decision over the events it is handed; never resumed |
| `agent_os/bin/puntal_task.sh --action A --node-file N [...]`, `--json [--plan-only]`, `feedback ...` | an app's UI or shell, a bench | answers one live UI action from its node slice: the node's declared reads are loaded by code, the model plans in one turn with no tool, the app's executor applies the operations; response on stdout (or one JSON envelope with `--json`), one telemetry line per call; `feedback` records the owner's verdict (§4.7). Not a role the planner launches |
| `bench/puntal/measure.py calibrate\|main\|reserve\|summarize\|status` | the lead, once, deliberately | the puntal spike's measurement; the only place real calls are authorised, capped at 30 in code (§4.7) |
| `agent_os.guard check <backend> [--slot N]\|tick\|wake\|promote-refined\|event` | exit hook (`check`), systemd timer (`tick`), `wake`/drivers (`event`), a human (`promote-refined`, by hand), or control-plane via `issues.py update --add-label wake:planner` (never this script directly) | exit-hook bookkeeping; the periodic budget/liveness/quota/drift check, which also reconciles mechanical state (closed → `done`, `promote_refined`, `orphan_doing`) and reports a one-shot role run whose PID is dead with its PID file still on disk as `role_died` (#400); advances `merged_seen.json` and may write `pr_merged`; removes any `wake:planner` label found and may write `nudged` (#413); the `flock`-guarded planner invocation; write a `<kind>` event; the `status:refine → status:ready` sweep, which the tick now runs on every fire |
| `agent_os/bin/notify.sh "<message>"` | guard, planner | one ntfy.sh POST to the project's single topic |
| `agent_os/bin/worker_progress.sh [issue] [--hours H]` | human | what the workers have done lately and what they have spent, in one screen |
| `systemctl --user status\|start\|stop <guard>.service\|.timer` | human | inspect or force the tick; arm/disarm the schedule — always a human decision |
