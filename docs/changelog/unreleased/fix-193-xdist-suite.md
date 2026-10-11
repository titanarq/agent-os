- The suite runs in parallel (#193): `pytest-xdist` joins the dev dependencies and `bootstrap.sh`; the CI suite step and
  `bin/dev/run_suite.sh` use `-n 6` (a caller's own `-n`, e.g. `-n 0`, overrides it in `run_suite.sh`). Measured on an
  8-core machine under load: 40.5 min serial against 9.2 and 9.4 min with `-n 6`, 2101 passed and 0 failed in all three.
  The suite itself is unchanged and still runs whole.
