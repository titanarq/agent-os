"""The integrator: lands a group of ready pull requests under one CI, one at a time when in doubt
(`docs/adr/2026-10-11-the-integrator-lands-a-group-of-ready-prs-under-one-ci-and-one-at-a-time-when-in-doubt.md`).

- `facts` -- what `gh` and `git` say about one pull request; a fact it cannot read is recorded as
  unreadable, never guessed.
- `rules` -- which pull requests are candidates, what keeps one out of any group, and the greedy,
  oldest-first group of one round.
- `judge` -- the one model turn that confirms, splits or sends solo the group the rules allowed.
- `plan` and `cli` -- the dry run `agent-os-integrate plan`, which writes nothing to GitHub.
"""
