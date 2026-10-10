"""One click's request and the options everything else resolves to, refused loudly when it cannot be."""

from __future__ import annotations

import argparse
import dataclasses
import os
import pathlib
import shlex
import sys
import uuid

from agent_os.lib import (
    CONFIG_LOAD_ERRORS,
    backend_config,
    config_load_failure,
    load_agents_config,
    load_role_class,
    prompt_extras_path,
    render_prompt,
)
from agent_os.product.puntal.constants import (
    FAST_PATH_API_INTRODUCTION,
    PATH_FAST,
    PATH_SLOW,
    PUNTAL_ROLE,
    SLOW_PATH_PROMPT,
    STATE_COMMAND,
    SUPPORTED_STREAM,
    PuntalRefused,
)
from agent_os.product.puntal.fast.pre_helper import split_node_declaration
from agent_os.product.puntal.stream.events import Ceilings
from agent_os.product.puntal.stream.launch import backend_executable_for


@dataclasses.dataclass(frozen=True)
class Request:
    action: str
    node_id: str
    node_slice: str
    payload: str
    relevant_state: str
    session_id: str
    invocation_id: str
    labels: dict[str, str]
    # What the node declares its action reads (its frontmatter, and the caller's own `--read`s).
    declared_reads: list[str] = dataclasses.field(default_factory=list)
    declaration_problems: list[str] = dataclasses.field(default_factory=list)
    # A plan the caller applied itself and that failed: `{"plan": ..., "errors": [...]}`.
    previous_attempt: dict | None = None
    # Who clicked, for the app's own commands (`PUNTAL_ACTOR`, `fast/actor.py`); empty names nobody.
    actor: str = ""


@dataclasses.dataclass(frozen=True)
class Options:
    class_name: str
    backend: str
    model: str
    effort: str
    persistence_command: str
    executor_command: str
    read_subcommands: tuple[str, ...]
    executor_timeout_seconds: int
    ceilings: Ceilings
    executable: str
    run_dir: pathlib.Path
    telemetry_file: pathlib.Path
    host_root: pathlib.Path
    fast_contract: str
    slow_contract: str
    # `fast`: plan in one turn, code executes. `slow`: forced tool loop, for a node nobody has taught
    # to declare its reads yet and for the bench's baseline.
    path: str
    plan_only: bool


def run_dir_for(host_root: pathlib.Path) -> pathlib.Path:
    """Where the puntal's per-run logs, `runs.tsv`, default telemetry and feedback live:
    `AGENT_CACHE_DIR` whole, exactly as every one-shot role's driver and the guard read it, else
    `.cache/puntal`."""
    override = os.environ.get("AGENT_CACHE_DIR")
    return pathlib.Path(override) if override else host_root / ".cache" / PUNTAL_ROLE


def _render_contracts(config, host_root: pathlib.Path) -> tuple[str, str]:
    puntal = config.puntal
    api_text = ""
    if puntal.persistence_api_file:
        api_path = host_root / puntal.persistence_api_file
        if not api_path.is_file():
            raise PuntalRefused(
                f"puntal.persistence_api_file names {api_path}, which is not a file"
            )
        api_text = api_path.read_text()
    extras = prompt_extras_path(PUNTAL_ROLE, config.project)
    try:
        # The API text goes in first, so that it may use `__STATE_COMMAND__` itself. Both paths
        # get it: the slow one to call it, the fast one to know what its operations apply to.
        fast = render_prompt(
            PUNTAL_ROLE,
            {
                "PERSISTENCE_API": FAST_PATH_API_INTRODUCTION + api_text if api_text else "",
                "STATE_COMMAND": STATE_COMMAND,
            },
            extras,
        )
        slow = render_prompt(
            SLOW_PATH_PROMPT,
            {"PERSISTENCE_API": api_text, "STATE_COMMAND": STATE_COMMAND},
            extras,
        )
    except (KeyError, FileNotFoundError) as error:
        raise PuntalRefused(str(error.args[0])) from error
    return fast, slow


def resolve_options(*, args: argparse.Namespace, host_root: pathlib.Path, action: str) -> Options:
    """Everything config answers, resolved once and refused loudly: a puntal that cannot be run as
    configured must not reach a backend. The model is the `--model` flag's, else the one
    `puntal.action_models` names for `action`, else the puntal class's."""
    try:
        config = load_agents_config()
        class_name, task_class = load_role_class(PUNTAL_ROLE)
    except CONFIG_LOAD_ERRORS as error:
        raise PuntalRefused(config_load_failure(error)) from error
    except KeyError as error:
        raise PuntalRefused(str(error.args[0])) from error
    puntal = config.puntal
    backend = backend_config(task_class.backend, project=config.project)
    if backend.stream != SUPPORTED_STREAM:
        raise PuntalRefused(
            f"the puntal class runs on backend '{task_class.backend}', whose stream is "
            f"'{backend.stream}': the tool confinement here is the {SUPPORTED_STREAM} CLI's"
        )
    persistence_command = (
        args.persistence_command
        or os.environ.get("PUNTAL_PERSISTENCE_COMMAND")
        or puntal.persistence_command
    ).strip()
    if not persistence_command:
        raise PuntalRefused(
            "no persistence command: set puntal.persistence_command, PUNTAL_PERSISTENCE_COMMAND or "
            "--persistence-command. State is real from day one (docs/AGENTOS_V2_PLAN.md, founding "
            "decision 4): a puntal that cannot persist contradicts itself between sessions"
        )
    executor_command = (
        args.executor_command
        or os.environ.get("PUNTAL_EXECUTOR_COMMAND")
        or puntal.executor_command
    ).strip()
    path = args.path or PATH_FAST
    plan_only = bool(getattr(args, "plan_only", False))
    if path == PATH_FAST and not executor_command and not plan_only:
        raise PuntalRefused(
            "no executor command: the fast path hands the plan's operations to the app's code. Set "
            "puntal.executor_command, PUNTAL_EXECUTOR_COMMAND or --executor-command, ask for "
            "--json --plan-only to apply them yourself, or run --path slow"
        )
    fast_contract, slow_contract = _render_contracts(config, host_root)
    run_dir = run_dir_for(host_root)
    return Options(
        class_name=class_name,
        backend=task_class.backend,
        model=args.model or puntal.action_models.get(action) or task_class.model,
        effort=args.effort if args.effort is not None else puntal.effort,
        persistence_command=persistence_command,
        executor_command=executor_command,
        read_subcommands=tuple(puntal.read_subcommands),
        executor_timeout_seconds=puntal.executor_timeout_seconds,
        ceilings=Ceilings(
            max_context=task_class.max_context,
            max_cost_usd=task_class.max_cost_usd,
            max_total_tokens=task_class.max_total_tokens,
            max_tool_calls=puntal.max_tool_calls,
            timeout_seconds=args.timeout or puntal.timeout_seconds,
        ),
        executable=backend_executable_for(task_class.backend, config.project),
        run_dir=run_dir,
        telemetry_file=pathlib.Path(args.telemetry_file)
        if args.telemetry_file
        else run_dir / "telemetry.jsonl",
        host_root=host_root,
        fast_contract=fast_contract,
        slow_contract=slow_contract,
        path=path if path in (PATH_FAST, PATH_SLOW) else PATH_FAST,
        plan_only=plan_only,
    )


def read_text(source: str | None, *, what: str) -> str:
    if source is None:
        return ""
    if source == "-":
        return sys.stdin.read()
    path = pathlib.Path(source)
    if not path.is_file():
        raise PuntalRefused(f"{what} {source!r} is not a file")
    return path.read_text()


def parse_labels(assignments: list[str]) -> dict[str, str]:
    labels = {}
    for assignment in assignments:
        key, separator, value = assignment.partition("=")
        if not separator or not key:
            raise PuntalRefused(f"--label takes KEY=VALUE, and {assignment!r} is not")
        labels[key] = value
    return labels


def build_request(args: argparse.Namespace) -> Request:
    if args.payload is not None and args.payload_file is not None:
        raise PuntalRefused("give the payload with --payload or --payload-file, not both")
    node_text = read_text(args.node_file, what="the node file")
    if not node_text.strip():
        raise PuntalRefused(
            "the node slice is empty: a puntal without a node has no behaviour to follow"
        )
    declaration = split_node_declaration(node_text)
    node_id = args.node_id or (
        pathlib.Path(args.node_file).stem if args.node_file not in (None, "-") else ""
    )
    if not node_id:
        raise PuntalRefused("--node-id is required when the node slice comes from stdin")
    return Request(
        action=args.action,
        node_id=node_id,
        node_slice=declaration.slice_text,
        payload=args.payload
        if args.payload is not None
        else read_text(args.payload_file, what="the payload file"),
        relevant_state=read_text(args.state_file, what="the state file"),
        session_id=args.session_id or "",
        invocation_id=args.invocation_id or str(uuid.uuid4()),
        labels=parse_labels(args.label),
        declared_reads=[*declaration.reads, *(r.strip() for r in args.read)],
        declaration_problems=declaration.problems,
    )


def shell_words(command: str) -> list[str]:
    return shlex.split(command)
