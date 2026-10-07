"""The versions every record carries (model, CLI version, method version) and the one-line JSON
log the puntal's telemetry and feedback -- and the judgments log after them -- append to.

Pure filesystem and git. This file must not request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import threading

import pytest

from agent_os.product.records import append_json_line, record_versions
from agent_os.product.records.versions import agent_os_commit, prompt_digest


def git(directory: pathlib.Path, *arguments: str) -> str:
    environment = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "HOME": str(directory),
        "PATH": "/usr/bin:/bin",
    }
    return subprocess.run(
        ["git", "-C", str(directory), *arguments],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def make_repository(directory: pathlib.Path) -> str:
    directory.mkdir(parents=True)
    git(directory, "init", "-q", "-b", "main")
    (directory / "file.txt").write_text("one")
    git(directory, "add", ".")
    git(directory, "commit", "-q", "-m", "first")
    return git(directory, "rev-parse", "HEAD")


def test_the_digest_of_a_prompt_is_stable_and_tells_two_prompts_apart():
    assert prompt_digest("a prompt") == prompt_digest("a prompt")
    assert prompt_digest("a prompt") != prompt_digest("a prompt.")
    assert (
        prompt_digest("x").startswith("sha256:") and len(prompt_digest("x")) == len("sha256:") + 16
    )


def test_a_checkout_of_agent_os_reports_its_own_head(tmp_path):
    head = make_repository(tmp_path / "agent-os")
    assert agent_os_commit(tmp_path / "agent-os") == head


@pytest.mark.skipif(shutil.which("git") is None, reason="git is needed")
def test_a_host_subtree_reports_the_upstream_commit_it_was_pulled_from(tmp_path):
    upstream = tmp_path / "upstream"
    upstream_head = make_repository(upstream)
    host = tmp_path / "host"
    make_repository(host)
    git(host, "subtree", "add", "--prefix=agent_os", str(upstream), "main", "--squash")
    assert agent_os_commit(host / "agent_os") == upstream_head


def test_a_directory_in_no_repository_has_no_commit_and_says_so_without_failing(tmp_path):
    (tmp_path / "loose").mkdir()
    assert agent_os_commit(tmp_path / "loose") is None


def test_record_versions_carries_the_three_versions_of_the_plan(tmp_path):
    head = make_repository(tmp_path / "agent-os")
    versions = record_versions(
        model="claude-sonnet-5-5",
        cli_version="2.1.289",
        prompt_text="the contract",
        agent_os_dir=tmp_path / "agent-os",
    )
    assert versions == {
        "model": "claude-sonnet-5-5",
        "cli_version": "2.1.289",
        "method_version": {"agent_os_commit": head, "prompt_digest": prompt_digest("the contract")},
    }


def test_append_json_line_writes_one_line_per_record_even_from_many_threads(tmp_path):
    target = tmp_path / "deep" / "log.jsonl"
    threads = [
        threading.Thread(target=append_json_line, args=(target, {"n": n, "text": "é" * 2000}))
        for n in range(20)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    lines = target.read_text(encoding="utf-8").splitlines()
    assert sorted(json.loads(line)["n"] for line in lines) == list(range(20))
