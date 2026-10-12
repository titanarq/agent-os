"""`agent-os-integrate plan --prs N N N [--format summary|json]`: the dry run of a round.

    agent-os-integrate plan --prs N N N [--format summary|json] [--root DIR] [--config PATH]

Read-only: it reads each pull request through `gh` and `git fetch`, and changes nothing on GitHub.
Exit 0 and the plan; 2 when the plan could not be made at all (no repository, no default branch)."""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections.abc import Sequence

from agent_os import lib
from agent_os.product.integrator.facts import run_command_in
from agent_os.product.integrator.plan import TestSelectionInputs, plan_round, render
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        repository = git_toplevel_of(arguments.root or pathlib.Path.cwd()).resolve()
        integrator, inputs, repo_flags = _load_settings(arguments.config, repository)
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
    except (GitError, ManifestError, ManifestNotFoundError, *lib.CONFIG_LOAD_ERRORS) as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        return COULD_NOT_RUN
    print(render(plan, arguments.format))
    return 0


if __name__ == "__main__":
    sys.exit(main())
