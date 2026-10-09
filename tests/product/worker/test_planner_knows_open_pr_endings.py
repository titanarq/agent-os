"""The planner prompt says what to do with every ending `open-pr` can write as `BLOCKED reason=...`.

Those endings reach the planner as a `worker_cut` event, and nothing else in its prompt describes
them: it read them as a cut stage and could relaunch a run whose work was finished. The reasons are
read from the drivers, so a reason added to `open-pr` without a line for the planner fails here.
"""

from __future__ import annotations

import re

from agent_os.cli import AGENT_OS_DIR

BLOCKED_STATE_WRITTEN = re.compile(r"write_state \"BLOCKED reason=(?P<reason>[a-z_]+)[ \"]")
PUSH_REJECTION_CLASSIFIED = re.compile(r"push_rejection=(?P<reason>[a-z_]+)$", re.MULTILINE)
DRIVER_FILES = ("worker_task.sh", "worker/worker_publication_refusals.sh")
PLANNER_PROMPT = AGENT_OS_DIR / "prompts" / "planner.md"


def reasons_open_pr_can_end_with() -> set[str]:
    reasons = set()
    for name in DRIVER_FILES:
        text = (AGENT_OS_DIR / "bin" / name).read_text()
        reasons |= {match["reason"] for match in BLOCKED_STATE_WRITTEN.finditer(text)}
        reasons |= {match["reason"] for match in PUSH_REJECTION_CLASSIFIED.finditer(text)}
    return reasons


def test_the_drivers_still_write_the_endings_this_file_reads():
    assert {"push_rejected", "malformed_node_change_trailer"} <= reasons_open_pr_can_end_with()


def test_the_planner_prompt_names_every_ending_open_pr_can_write():
    prompt = PLANNER_PROMPT.read_text()
    unnamed = sorted(
        reason for reason in reasons_open_pr_can_end_with() if f"`{reason}`" not in prompt
    )
    assert unnamed == []


def test_the_planner_is_told_to_tell_the_human_and_not_to_retry_blindly():
    prompt = " ".join(PLANNER_PROMPT.read_text().split())
    assert "ends as a `worker_cut` reading `BLOCKED reason=<reason>`" in prompt
    assert "no cut stage -- never `resume` it nor re-run `open-pr` blindly" in prompt
    assert (
        "Make sure it is `status:blocked-on-human` and mention the human with the reason" in prompt
    )
