"""The integrator's one model step: judging whether the group the rules allowed is independent in
meaning. One turn, no tool, an index and no diff; whatever goes wrong sends every pull request solo.

- `index` -- the pull requests of the group as the model reads them, and the brief built from them.
- `evidence` -- reads the facts the index needs from GitHub and git.
- `verdict` -- the model's answer, validated against what the script allowed.
- `options` and `run` -- the class `integrator` resolved into the puntal's `Options`, and the turn.
- `round` -- `agent-os-integrate plan --judge`: index, turn and the final groups.
- `cli` -- `bin/integrator_task.sh judge`: the same on a request read from stdin.
"""
