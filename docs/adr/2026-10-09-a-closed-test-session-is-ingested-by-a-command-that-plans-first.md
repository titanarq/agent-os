# A closed test session is ingested by a command that plans first

Date: 2026-10-09. Tree: `docs/tree/uc-open-a-test-session-for-a-branch.md` (mechanism: "accepted interactions
harden the specification; rejected ones return as rework or as questions of what; answers are written back"),
`dec-a-test-session-happens-inside-the-app`, `dec-a-change-to-the-what-is-merged-only-on-the-owners-word`,
`dec-use-orders-hardening-and-the-owner-order-wins`, `dec-tests-harden-they-do-not-build`,
`dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check`.

## Context

The first v2 host writes a closed session's result to a file and, on purpose, never touches the tree. Nothing in
Agentos read that file, so what the owner said in the app stopped at the app.

## Decision

1. **The file is a contract Agentos documents** (`docs/AGENT_OS.md` §4.11), its directory a config key,
   `tree.test_sessions_dir`, with a documented default and never a host's path. A missing directory is refused,
   naming the key.
2. **One command, `agent-os-sessions test-ingest`, plans by default.** It prints what each not-yet-ingested closed
   session would change and writes nothing; `--apply` does it. The plan is a pure function of the session, the
   tree and the tracker, so what is shown is what is done. An open session is nobody's input.
3. **Answers use the path of the question session**: the same edit (`writeback.answer_question`), left in the
   working tree for a worker to commit with `Node-Change: usage` and a pull request marked `Test-Session: <id>`.
   `owner` stays the one value an agent never writes: the owner's word is transcribed, not given. The pull request
   changes the what and is merged on the owner's word. An unanswered question is left alone: its default stands.
4. **A rejection is always a rework ticket**, never a guessed question of what. Free text does not say reliably
   whether the owner asked to fix or to decide; a wrong guess would put an invented question in front of the owner
   or hide a defect. The ticket quotes the note whole, names the session as source, and tells the worker to record
   a question of what instead when the note asks to decide. The expert can reclassify.
5. **An acceptance is a field of the node**, `acceptances: [{session, date}]`, once per session. In the node and
   not in a side log so that it travels with the node's history, is read by the same loader as everything else, and
   is what the hardening order counts. Evidence, not a change of the what.
6. **Idempotency is per effect; the registry is only a shortcut.** Answers are skipped once answered with those
   words, an acceptance is recorded once per session, a ticket is found by `<!-- key: test-rework.<session>.<node> -->`
   before another is opened. The registry (`.cache/test-sessions/ingested.jsonl`) lives in the cache, not in git:
   losing it costs a longer plan and never a duplicate, and keeping it in git would make the bookkeeping a pull
   request on the tree. A session with a problem is not registered and stays pending.
7. **The verdicts on improvised answers are input, not yet action.** Those of `feedback.jsonl` inside the
   session's window are summarised in the plan; the window is the only join the two files have.

## Rejected alternatives

- *Open the pull request from the command.* Left to the planner's worker as with `apply`: committing and merging
  are the control plane's, and the command stays testable without git or a network.
- *The registry in git.* See 6.
- *Acceptance as an experiment.* An experiment records a doubt settled by evidence; an accepted case is not a doubt.

## Review triggers

A host whose product cannot write the file as the contract says; a second product whose notes are structured
enough to tell rework from a question; a hardening order that needs more than a count of acceptances.
