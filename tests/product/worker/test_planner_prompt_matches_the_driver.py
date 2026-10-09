"""The planner prompt describes what the worker driver does today, not the route it replaced.

Stage 1i made the rework of a pull request sent back with CHANGES_REQUESTED a step of the driver
(`resume --issue N --rework`); the prompt kept telling the planner to paste the review by hand into
`--after manual --context`, a route that fails for a run whose every stage is committed. Stage 1k
also records the quota verdict a stage exit reads (`quota_verdict`), which the prompt now says.
"""

from __future__ import annotations

from agent_os.cli import AGENT_OS_DIR

PLANNER_PROMPT = AGENT_OS_DIR / "prompts" / "planner.md"
DRIVER = AGENT_OS_DIR / "bin" / "worker_task.sh"
REWORK_STAGE_TITLE = "Address the changes requested on PR #"


def prompt_words() -> str:
    return " ".join(PLANNER_PROMPT.read_text().split())


def test_the_planner_sends_a_requested_change_back_through_rework():
    prompt = prompt_words()
    assert "worker_task.sh <backend> resume --issue <N> --rework" in prompt
    assert f"`{REWORK_STAGE_TITLE}<n>`" in prompt


def test_the_planner_no_longer_pastes_the_review_by_hand():
    prompt = prompt_words()
    assert '--context "<that body>"' not in prompt
    assert "'.reviews[-1].body'" not in prompt
    assert "never edit `## Stages` or paste the review" in prompt


def test_the_rework_the_prompt_names_is_one_the_driver_parses_and_titles_the_same_way():
    assert "--rework)" in DRIVER.read_text()
    rework_module = AGENT_OS_DIR / "agent_os" / "product" / "tracker" / "rework.py"
    assert REWORK_STAGE_TITLE in rework_module.read_text()


def test_the_planner_is_told_the_quota_verdict_persists_and_lapses_by_itself():
    prompt = prompt_words()
    assert "persisted one, which a quota cut's own `stage-exit` writes too" in prompt
    assert "never probe an exhausted window by launching into it" in prompt
