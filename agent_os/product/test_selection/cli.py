"""`agent-os-tests check|plan|run`: the tests a branch must run, from the manifest and the diff.

    agent-os-tests check [--manifest PATH]
    agent-os-tests plan --base REF [--manifest PATH] [--tree-root DIR] [--format summary|json|paths]
                        [--last-full-run ISO8601|never|unknown] [--interval-hours N] [--only-when-due]
    agent-os-tests run --base REF [--manifest PATH] [--command CMD] [--full]
                       [--last-full-run ...] [--interval-hours N] [--only-when-due]
    agent-os-tests last-full-run --repo OWNER/REPO [--marker-name NAME]

The repository judged is the checkout of the working directory (or `--root`), never the host's
main checkout named by `AGENT_OS_HOST_ROOT`. `check`: exit 0 clean (or selection off), 1 defects,
2 could not run. `plan`: exit 0 and the plan, 1 invalid manifest, 2 could not run. `run`: the
runner's own exit code (0 for mode `none`); a plan that could not be computed runs the whole suite, because a failed
tool must not skip tests."""

from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from agent_os import lib
from agent_os.product.test_selection.changed_paths import changed_paths
from agent_os.product.test_selection.checks import check_manifest
from agent_os.product.test_selection.clock.ci_outputs import publish_plan_to_github
from agent_os.product.test_selection.clock.clock_plan import plan_under_clock
from agent_os.product.test_selection.clock.last_full_run import (
    DEFAULT_MARKER_NAME,
    read_last_full_run,
)
from agent_os.product.test_selection.manifest import (
    Manifest,
    ManifestError,
    ManifestNotFoundError,
    load_manifest,
)
from agent_os.product.test_selection.manifest_changes import (
    describe_manifest_change,
    manifest_files_changed,
)
from agent_os.product.test_selection.node_changes import (
    ancestors_by_node_id,
    node_ids_by_changed_path,
)
from agent_os.product.test_selection.plan import (
    SELECTION_IS_OFF,
    TestPlan,
    full_plan_because_off,
    plan_tests,
)
from agent_os.quality.git_snapshots import GitError, git_toplevel_of, merge_base_with_head

PROGRAM = "agent-os-tests"
COULD_NOT_RUN = 2


@dataclass
class _Settings:
    repository: pathlib.Path
    manifest_path: str
    tree_root: str
    test_command: str | None
    full_run_interval_hours: int = 4


def _read_settings(arguments: argparse.Namespace) -> _Settings:
    repository = git_toplevel_of(arguments.root or pathlib.Path.cwd()).resolve()
    path = arguments.config or lib.DEFAULT_AGENTS_CONFIG
    manifest_path = tree_root = ""
    test_command = None
    interval_hours = _Settings.full_run_interval_hours
    if arguments.config is not None or path.exists():
        loaded = lib.load_agents_config(path)
        manifest_path = loaded.project.test_selection.manifest
        tree_root = loaded.tree.root
        test_command = loaded.project.test_command
        interval_hours = loaded.project.test_selection.full_run_interval_hours
    return _Settings(
        repository,
        arguments.manifest or manifest_path,
        getattr(arguments, "tree_root", None) or tree_root,
        test_command,
        interval_hours,
    )


def compute_plan(settings: _Settings, base_reference: str) -> TestPlan:
    if not settings.manifest_path:
        return full_plan_because_off()
    manifest = load_manifest(settings.repository, settings.manifest_path)
    paths = changed_paths(settings.repository, base_reference)
    manifest_change = None
    if manifest_files_changed(paths, settings.manifest_path):
        merge_base = merge_base_with_head(settings.repository, base_reference)
        manifest_change = describe_manifest_change(
            settings.repository, merge_base, manifest, settings.manifest_path
        )
    return plan_tests(
        manifest,
        paths,
        node_ids_by_changed_path(paths, settings.tree_root),
        ancestors_by_node_id(settings.repository, settings.tree_root),
        manifest_change,
    )


def compute_plan_under_clock(settings: _Settings, arguments: argparse.Namespace) -> TestPlan:
    return plan_under_clock(
        arguments.last_full_run,
        arguments.interval_hours or settings.full_run_interval_hours,
        arguments.only_when_due,
        datetime.now(UTC),
        lambda: compute_plan(settings, arguments.base),
    )


def _print_plan(plan: TestPlan, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(asdict(plan), indent=2))
    elif output_format == "paths":
        print("\n".join(plan.tests if plan.mode == "selected" else ()))
    else:
        print(plan.summary())


def _command_check(arguments: argparse.Namespace, settings: _Settings) -> int:
    if not settings.manifest_path:
        print(SELECTION_IS_OFF)
        return 0
    try:
        manifest: Manifest = load_manifest(settings.repository, settings.manifest_path)
    except ManifestError as error:
        print(error)
        return 1
    defects = check_manifest(manifest, settings.repository)
    print("\n".join(defects))
    return 1 if defects else 0


def _command_plan(arguments: argparse.Namespace, settings: _Settings) -> int:
    try:
        plan = compute_plan_under_clock(settings, arguments)
    except (ManifestError, ValueError) as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        return 1
    _print_plan(plan, arguments.format)
    return 0


def _command_run(arguments: argparse.Namespace, settings: _Settings) -> int:
    command = arguments.command or settings.test_command
    if not command:
        raise ManifestNotFoundError("no test command: pass --command or set `project.test_command`")
    if arguments.full:
        plan = TestPlan("full", "--full was given")
    else:
        try:
            plan = compute_plan_under_clock(settings, arguments)
        except (ManifestError, ValueError) as error:
            print(f"{PROGRAM}: {error}", file=sys.stderr)
            return 1
        except (GitError, ManifestNotFoundError, OSError) as error:
            print(f"{PROGRAM}: running the whole suite, the plan failed: {error}", file=sys.stderr)
            plan = TestPlan("full", "the plan could not be computed")
    print(plan.summary(), flush=True)
    publish_plan_to_github(plan)
    if plan.mode == "none" or (plan.mode == "selected" and not plan.tests):
        return 0
    selected_paths = list(plan.tests) if plan.mode == "selected" else []
    return subprocess.run([*shlex.split(command), *selected_paths], check=False).returncode


def _command_last_full_run(arguments: argparse.Namespace) -> int:
    print(read_last_full_run(arguments.repo, arguments.marker_name))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=pathlib.Path, help="a directory of the repository")
    parser.add_argument("--config", type=pathlib.Path, help="config/agents.yaml to read")
    commands = parser.add_subparsers(dest="command_name", required=True)
    last_run = commands.add_parser("last-full-run")
    last_run.add_argument("--repo", required=True, help="OWNER/REPO whose Actions are read")
    last_run.add_argument("--marker-name", default=DEFAULT_MARKER_NAME)
    for name in ("check", "plan", "run"):
        sub = commands.add_parser(name)
        sub.add_argument("--manifest", help="the manifest, relative to the repository root")
        if name != "check":
            sub.add_argument("--base", required=True, help="the ref the pull request targets")
        if name != "check":
            sub.add_argument("--last-full-run", help="ISO8601, `never` or `unknown`")
            sub.add_argument("--interval-hours", type=float, help="default: project config")
            sub.add_argument("--only-when-due", action="store_true")
        if name == "plan":
            sub.add_argument("--tree-root", help="the product tree's folder")
            sub.add_argument("--format", choices=("summary", "json", "paths"), default="summary")
        if name == "run":
            sub.add_argument("--command", help="default: project.test_command")
            sub.add_argument("--full", action="store_true", help="the whole suite regardless")
    return parser


_COMMANDS = {"check": _command_check, "plan": _command_plan, "run": _command_run}


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command_name == "last-full-run":
            return _command_last_full_run(arguments)
        settings = _read_settings(arguments)
        return _COMMANDS[arguments.command_name](arguments, settings)
    except (
        GitError,
        ManifestNotFoundError,
        *lib.CONFIG_LOAD_ERRORS,
    ) as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        return COULD_NOT_RUN


if __name__ == "__main__":
    sys.exit(main())
