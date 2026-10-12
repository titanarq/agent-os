"""`agent-os-integrate plan|build --prs N N N`: the dry run of a round, and its integration branch.

    agent-os-integrate build --prs N N N [--dry-run]   (steps 1-4 of the ADR; exit 1: not built)
    agent-os-integrate build --prs N N N --without N     (the rebuild after `evict #N`)
    agent-os-integrate result <integration PR> [--summary-index suite.summary.json]
        waits for the integration head's checks; prints `passed`, `evict #N` or `solo: <why>`
    agent-os-integrate land <integration PR>
        merges each member through `safe_merge.sh --group`, checks the trees, closes the integration PR
    agent-os-integrate plan --prs N N N [--format summary|json] [--judge] [--root DIR] [--config PATH]
        --judge runs the one model turn on the group (bin/integrator_task.sh's judgment) and prints the
        final groups with its reasons; anything it cannot answer leaves every pull request alone

Read-only: it reads each pull request through `gh` and `git fetch`, and changes nothing on GitHub.
Exit 0 and the plan; 2 when the plan could not be made at all (no repository, no default branch)."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Sequence

from agent_os import lib
from agent_os.product.integrator.build import build_integration
from agent_os.product.integrator.facts import run_command_in
from agent_os.product.integrator.judge.round import judge_round
from agent_os.product.integrator.plan import TestSelectionInputs, plan_round, render
from agent_os.product.integrator.result.attribution import SummaryIndexError
from agent_os.product.integrator.result.landing import land_group
from agent_os.product.integrator.result.verdict import decide_round
from agent_os.product.integrator.round_lock import IntegrationInFlightError
from agent_os.product.shared.config import IntegratorConfig
from agent_os.product.test_selection.manifest import (
    ManifestError,
    ManifestNotFoundError,
    load_manifest,
)
from agent_os.product.test_selection.node_changes import ancestors_by_node_id
from agent_os.quality.git_snapshots import GitError, git_toplevel_of

PROGRAM = "agent-os-integrate"
COULD_NOT_RUN = 2
NOT_BUILT = 1
NOT_LANDED = 1


def _load_settings(config_path: pathlib.Path | None, repository: pathlib.Path):
    path = config_path or lib.DEFAULT_AGENTS_CONFIG
    if config_path is None and not path.exists():
        return IntegratorConfig(), TestSelectionInputs(None, "", "", {}), []
    loaded = lib.load_agents_config(path)
    manifest_path = loaded.project.test_selection.manifest
    tree_root = loaded.tree.root
    manifest = load_manifest(repository, manifest_path) if manifest_path else None
    inputs = TestSelectionInputs(
        manifest, manifest_path, tree_root, ancestors_by_node_id(repository, tree_root)
    )
    return loaded.integrator, inputs, ["--repo", loaded.project.repo]


def _default_branch(run, repo_flags: list[str]) -> str:
    answer = run(
        [
            "gh",
            "repo",
            "view",
            *repo_flags[1:],
            "--json",
            "defaultBranchRef",
            "-q",
            ".defaultBranchRef.name",
        ]
    )
    if answer.returncode != 0 or not answer.stdout.strip():
        raise GitError(f"the default branch could not be read: {answer.stderr.strip()}")
    return answer.stdout.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=pathlib.Path, help="a directory of the repository")
    parser.add_argument("--config", type=pathlib.Path, help="config/agents.yaml to read")
    commands = parser.add_subparsers(dest="command_name", required=True)
    plan = commands.add_parser("plan", help="the candidates and the mechanical group, dry run")
    plan.add_argument("--prs", type=int, nargs="+", required=True, metavar="N")
    plan.add_argument("--format", choices=("summary", "json"), default="summary")
    plan.add_argument(
        "--judge", action="store_true", help="have the model judge whether the group is independent"
    )
    build = commands.add_parser("build", help="the integration branch and its pull request")
    build.add_argument("--prs", type=int, nargs="+", required=True, metavar="N")
    build.add_argument("--dry-run", action="store_true", help="print the commands, change nothing")
    build.add_argument("--without", type=int, nargs="+", default=[], metavar="N", help="evicted")
    result = commands.add_parser("result", help="wait for the integration CI, print the verdict")
    result.add_argument("integration_pr", type=int, metavar="PR")
    result.add_argument("--summary-index", type=pathlib.Path, help="the run's suite.summary.json")
    land = commands.add_parser("land", help="merge a passed group's members, one merge commit each")
    land.add_argument("integration_pr", type=int, metavar="PR")
    return parser


def _command_land(arguments, repository, repo_flags) -> int:
    path = arguments.config or lib.DEFAULT_AGENTS_CONFIG
    merge_method = lib.load_agents_config(path).project.merge_method if path.exists() else "merge"
    landed = land_group(
        repository,
        run_command_in(repository),
        arguments.integration_pr,
        repo_flags,
        merge_method,
        print,
    )
    print(landed.line())
    if landed.failure:
        print(f"{PROGRAM}: {landed.failure}", file=sys.stderr)
        return NOT_LANDED
    return 0


def _command_build(arguments, repository, repo_flags) -> int:
    run = run_command_in(repository)
    result = build_integration(
        repository,
        run,
        arguments.prs,
        _default_branch(run, repo_flags),
        repo_flags,
        print,
        dry_run=arguments.dry_run,
        without=arguments.without,
    )
    for number, reason in result.left_solo.items():
        print(f"#{number} leaves the group, solo: {reason}")
    if result.failure:
        print(f"{PROGRAM}: {result.failure}", file=sys.stderr)
        return NOT_BUILT
    if result.pull_request is not None:
        print(result.line())
    return 0


def _command_result(arguments, repository, integrator, inputs, repo_flags) -> int:
    verdict = decide_round(
        repository,
        run_command_in(repository),
        arguments.integration_pr,
        repo_flags,
        inputs,
        integrator.ci_wait_max_minutes,
        arguments.summary_index,
    )
    print(verdict.line())
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        repository = git_toplevel_of(arguments.root or pathlib.Path.cwd()).resolve()
        integrator, inputs, repo_flags = _load_settings(arguments.config, repository)
        if arguments.command_name == "build":
            return _command_build(arguments, repository, repo_flags)
        if arguments.command_name == "land":
            return _command_land(arguments, repository, repo_flags)
        if arguments.command_name == "result":
            return _command_result(arguments, repository, integrator, inputs, repo_flags)
        run = run_command_in(repository)
        plan = plan_round(
            repository,
            run,
            arguments.prs,
            _default_branch(run, repo_flags),
            integrator,
            inputs,
            repo_flags,
        )
    except (
        IntegrationInFlightError,
        SummaryIndexError,
        GitError,
        ManifestError,
        ManifestNotFoundError,
        *lib.CONFIG_LOAD_ERRORS,
    ) as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        return COULD_NOT_RUN
    print(render(plan, arguments.format))
    if arguments.judge:
        judged = judge_round(repository, run, plan, repo_flags, judge_enabled=integrator.judge)
        print(
            json.dumps(judged.as_json(), indent=2)
            if arguments.format == "json"
            else judged.summary()
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
