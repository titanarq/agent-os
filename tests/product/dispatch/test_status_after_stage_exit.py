"""`status` after `stage-exit` archived the stage and emptied the live log."""

from __future__ import annotations

import subprocess

from test_worker_task import (
    DRIVER,
    ROOT,
    _archive_qwen_stage,
    _staged_body,
    _staged_environment,
)


def test_status_reads_the_latest_archived_stage_when_the_live_log_was_emptied(tmp_path):
    """`stage-exit` archives the finished stage under `.cache/spend/<issue>/` and empties the live
    log, so right after a stage `status` used to say "no events yet" about a run that had spent
    tokens. It now falls back to the newest archived stage of the issue and says so."""
    stage_titles = ("Write the failing test", "Make it pass")
    environment, cache, _worktree, _tmp = _staged_environment(
        tmp_path,
        stage_titles=stage_titles,
        mode="hang",
        subjects=("stage 1/2: Write the failing test",),
    )
    (cache / "worker_qwen.issue").write_text("347\n")
    (cache / "worker_qwen.stage").write_text("1/2\n")
    (cache / "worker_qwen.body.md").write_text(_staged_body(*stage_titles) + "\n")
    _archive_qwen_stage(cache, "qwen", 347, 1, total_tokens=600)
    (cache / "worker_qwen.jsonl").write_text("")

    status = subprocess.run(
        ["bash", str(DRIVER), "qwen", "status"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert status.returncode == 0, status.stdout + status.stderr
    assert "(no events yet)" not in status.stdout, status.stdout
    assert "(live log empty; showing the latest archived stage:" in status.stdout, status.stdout
    assert "  context" in status.stdout, status.stdout
    assert "600 tokens across every stage of #347" in status.stdout, status.stdout
