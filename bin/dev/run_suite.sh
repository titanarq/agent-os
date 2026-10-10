#!/usr/bin/env bash
# run_suite.sh <worktree> <outdir> [extra pytest args...] -- run the suite, read the INDEX, never the log.
# Leaves <outdir>/suite.summary.json (counts + one line per failure), suite.xml (junit, read per test
# with suite_show.py) and suite.raw.log (do not read it); prints one line. Launch it in the background.
set -uo pipefail
worktree=$1; output_directory=$2; shift 2; mkdir -p "$output_directory"
here=$(cd "$(dirname "$0")" && pwd)
cd "$worktree" || exit 2
TERM=dumb .venv/bin/pytest tests -q -p no:cacheprovider --tb=short --junitxml="$output_directory/suite.xml" "$@" > "$output_directory/suite.raw.log" 2>&1
exit_code=$?
python3 -I "$here/suite_index.py" "$output_directory/suite.xml" "$exit_code" > "$output_directory/suite.summary.json"
python3 -I -c 'import json,sys; s=json.load(open(sys.argv[1])); print("exit=%(exit)s passed=%(passed)s failed=%(failed)s errors=%(errors)s skipped=%(skipped)s secs=%(seconds)s" % s, "failing:", [f["id"] for f in s["failures"]][:10])' "$output_directory/suite.summary.json"
exit $exit_code
