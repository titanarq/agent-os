# Node CAL-T: calibration probe with one read

## Ancestor goals
- G0 (measurement): find the smallest context a puntal call can carry, and prove the persistence
  tool is reachable before anything real is spent on it.

## Use case
This is a probe, not a user action. Run `list tickets` through the persistence API exactly once and
change nothing. Answer with exactly `{"ok": true}`.
