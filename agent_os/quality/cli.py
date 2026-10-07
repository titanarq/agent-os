"""`agent-os-quality --base REF`: fails when the head makes the repository's shape worse.

    agent-os-quality --base origin/main [--root DIR] [--config PATH]

Exit 0: no folder or file is over a limit without having been so on the merge-base with REF, or
got worse since. Exit 1: violations, one line each. Exit 2: the check could not run."""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections.abc import Sequence

import yaml

from agent_os import lib
from agent_os.cli import AGENT_OS_DIR, host_root
from agent_os.quality.config import QualityConfig
from agent_os.quality.git_snapshots import (
    GitError,
    merge_base_with_head,
    snapshot_of_checkout,
    snapshot_of_revision,
)
from agent_os.quality.ratchet import Limits, find_violations

PROGRAM = "agent-os-quality"


def mechanism_directory_inside(repository: pathlib.Path) -> str | None:
    """The folder this package is vendored in when it lives below the repository (`agent_os/` in a
    host), which a host never edits; `None` when the package is the repository itself."""
    try:
        relative = AGENT_OS_DIR.resolve().relative_to(repository.resolve()).as_posix()
    except ValueError:
        return None
    return None if relative == "." else relative


def config_file_inside(repository: pathlib.Path, config_path: pathlib.Path) -> str | None:
    """The config file's path relative to the repository when it is tracked there (a host's
    `config/agents.yaml`), which is configuration and not code; `None` when it lives elsewhere."""
    try:
        return config_path.resolve().relative_to(repository.resolve()).as_posix()
    except ValueError:
        return None


def _load_quality_and_tree_root(
    config_path: pathlib.Path | None,
) -> tuple[QualityConfig, str, pathlib.Path | None]:
    """An explicit `--config` must load; the default one may simply not exist, as in the
    mechanism's own repository, which has no `config/agents.yaml`. The third value is the file
    that was read, `None` when there was none."""
    path = config_path or lib.DEFAULT_AGENTS_CONFIG
    if config_path is None and not path.exists():
        return QualityConfig(), "", None
    agents_config = lib.load_agents_config(path)
    return agents_config.quality, agents_config.tree.root, path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.split("\n")[0])
    parser.add_argument("--base", required=True, help="the ref the pull request targets")
    parser.add_argument("--root", type=pathlib.Path, help="the repository (default: the host's)")
    parser.add_argument(
        "--config", type=pathlib.Path, help="config/agents.yaml to read limits from"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    repository = (arguments.root or host_root()).resolve()
    try:
        quality, tree_root, loaded_config = _load_quality_and_tree_root(arguments.config)
        merge_base = merge_base_with_head(repository, arguments.base)
        excluded_paths = [*quality.excluded_paths, tree_root]
        excluded_paths.append(mechanism_directory_inside(repository) or "")
        if loaded_config is not None:
            excluded_paths.append(config_file_inside(repository, loaded_config) or "")
        violations = find_violations(
            snapshot_of_revision(repository, merge_base),
            snapshot_of_checkout(repository),
            Limits(quality.max_entries_per_folder, quality.max_lines_per_file),
            [path for path in excluded_paths if path],
        )
    except (GitError, *lib.CONFIG_LOAD_ERRORS, yaml.YAMLError) as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        return 2
    for violation in violations:
        print(violation.describe())
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
