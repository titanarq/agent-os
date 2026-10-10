"""suite_index.py <junit.xml> <exit-code> -- print a JSON index of a pytest run to stdout.

The index holds the counts and one line per failing test; run_suite.sh calls it so that nobody has to read the raw log.
"""

import json
import sys
from xml.etree import ElementTree

junit_path, exit_code = sys.argv[1], int(sys.argv[2])
counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
failures, seconds = [], 0.0
try:
    root = ElementTree.parse(junit_path).getroot()
except (OSError, ElementTree.ParseError) as problem:
    print(
        json.dumps(
            {
                "exit": exit_code,
                **counts,
                "seconds": 0,
                "failures": [],
                "note": f"no junit: {problem}",
            }
        )
    )
    sys.exit(0)
for case in root.iter("testcase"):
    seconds += float(case.get("time") or 0)
    test_id = f"{case.get('classname')}::{case.get('name')}"
    outcome = next((child for child in case if child.tag in ("failure", "error", "skipped")), None)
    if outcome is None:
        counts["passed"] += 1
    elif outcome.tag == "skipped":
        counts["skipped"] += 1
    else:
        counts["failed" if outcome.tag == "failure" else "errors"] += 1
        first_line = (outcome.get("message") or (outcome.text or "")).strip().splitlines()[:1]
        failures.append({"id": test_id, "message": (first_line[0] if first_line else "")[:200]})
print(
    json.dumps(
        {"exit": exit_code, **counts, "seconds": round(seconds), "failures": failures}, indent=1
    )
)
