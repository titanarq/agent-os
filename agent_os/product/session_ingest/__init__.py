"""The half of a test session that belongs to Agentos: what the owner decided inside the app,
carried into the tree and into the backlog (`docs/tree/uc-open-a-test-session-for-a-branch.md`,
`docs/adr/2026-10-09-a-closed-test-session-is-ingested-by-a-command-that-plans-first.md`).

The app writes a session file when the owner closes a session and never touches the tree. Here:

- `session_file` -- reads the closed session files (the contract is `docs/AGENT_OS.md` §4.11).
- `plan` -- what each closed session would change: answers, acceptances, rework.
- `rework_ticket` -- the dispatchable issue a rejected case returns as.
- `feedback_summary` -- the owner's verdicts on improvised answers during the session.
- `registry` -- which sessions were already ingested.
- `apply` -- executes a plan; `cli` -- the `test-ingest` subcommand of `agent-os-sessions`.
"""
