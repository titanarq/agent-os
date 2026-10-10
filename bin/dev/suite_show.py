"""suite_show.py <junit.xml> <test-id-substring> [max_lines=40] -- print only the failure text of the matching tests.

Reads the suite.xml that run_suite.sh leaves; the text is truncated to its last max_lines lines.
"""

import sys
from xml.etree import ElementTree

junit_path, wanted = sys.argv[1], sys.argv[2]
max_lines = int(sys.argv[3]) if len(sys.argv) > 3 else 40
for case in ElementTree.parse(junit_path).getroot().iter("testcase"):
    test_id = f"{case.get('classname')}::{case.get('name')}"
    if wanted not in test_id:
        continue
    for outcome in case:
        if outcome.tag in ("failure", "error"):
            lines = (outcome.text or outcome.get("message") or "").splitlines()
            print(f"== {test_id} ({outcome.tag}, {len(lines)} lines, showing the last {max_lines})")
            print("\n".join(lines[-max_lines:]))
