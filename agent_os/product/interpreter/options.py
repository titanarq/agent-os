"""Everything config answers, resolved once and refused loudly: an interpreter that cannot be run
as configured must not reach a backend. The result is the puntal's own `Options`, so the puntal's
turn runner, stream observer and telemetry run the interpreter unchanged."""

from __future__ import annotations

import os
import pathlib

from agent_os.lib import (
    CONFIG_LOAD_ERRORS,
    backend_config,
    config_load_failure,
    load_agents_config,
    load_role_class,
    prompt_extras_path,
    render_prompt,
)
from agent_os.product.config import InterpreterConfig
from agent_os.product.interpreter.constants import INTERPRETER_ROLE, InterpreterRefused
from agent_os.product.puntal.constants import PATH_FAST, SUPPORTED_STREAM
from agent_os.product.puntal.options import Options
from agent_os.product.puntal.stream.events import Ceilings
from agent_os.product.puntal.stream.launch import backend_executable_for

OWNERS_LANGUAGE = "the language the owner's latest message is written in"


def run_dir_for(host_root: pathlib.Path) -> pathlib.Path:
    """`AGENT_CACHE_DIR` whole, as every role's driver reads it, else `.cache/interpreter`."""
    override = os.environ.get("AGENT_CACHE_DIR")
    return pathlib.Path(override) if override else host_root / ".cache" / INTERPRETER_ROLE


def backend_executable(backend: str, project) -> str:
    """`INTERPRETER_<BACKEND>_BIN` (a test's override, derived from the name like the puntal's),
    else what the puntal resolves: its own override, the configured command, the bare name."""
    variable = "INTERPRETER_" + "".join(c if c.isalnum() else "_" for c in backend.upper()) + "_BIN"
    return os.environ.get(variable) or backend_executable_for(backend, project)


def resolve_options(
    *,
    host_root: pathlib.Path,
    model: str | None = None,
    timeout_seconds: int = 0,
    telemetry_file: str | None = None,
) -> tuple[Options, InterpreterConfig, pathlib.Path]:
    """`(options, interpreter config, tree root)`."""
    try:
        config = load_agents_config()
        class_name, task_class = load_role_class(INTERPRETER_ROLE)
        backend = backend_config(task_class.backend, project=config.project)
    except CONFIG_LOAD_ERRORS as error:
        raise InterpreterRefused(config_load_failure(error)) from error
    except KeyError as error:
        raise InterpreterRefused(str(error.args[0])) from error
    if backend.stream != SUPPORTED_STREAM:
        raise InterpreterRefused(
            f"the interpreter class runs on backend '{task_class.backend}', whose stream is "
            f"'{backend.stream}': its confinement here is the {SUPPORTED_STREAM} CLI's"
        )
    settings = config.interpreter
    try:
        contract = render_prompt(
            INTERPRETER_ROLE,
            {"REPLY_LANGUAGE": settings.reply_language.strip() or OWNERS_LANGUAGE},
            prompt_extras_path(INTERPRETER_ROLE, config.project),
        )
    except (KeyError, FileNotFoundError) as error:
        raise InterpreterRefused(str(error.args[0])) from error
    run_dir = run_dir_for(host_root)
    options = Options(
        class_name=class_name,
        backend=task_class.backend,
        model=model or task_class.model,
        effort=settings.effort,
        persistence_command="",
        executor_command="",
        read_subcommands=(),
        executor_timeout_seconds=0,
        ceilings=Ceilings(
            max_context=task_class.max_context,
            max_cost_usd=task_class.max_cost_usd,
            max_total_tokens=task_class.max_total_tokens,
            max_tool_calls=0,
            timeout_seconds=timeout_seconds or settings.timeout_seconds,
        ),
        executable=backend_executable(task_class.backend, config.project),
        run_dir=run_dir,
        telemetry_file=pathlib.Path(telemetry_file)
        if telemetry_file
        else run_dir / "telemetry.jsonl",
        host_root=host_root,
        fast_contract=contract,
        slow_contract="",
        path=PATH_FAST,
        plan_only=True,
    )
    return options, settings, host_root / config.tree.root
