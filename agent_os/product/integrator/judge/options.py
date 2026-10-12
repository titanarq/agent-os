"""The `integrator` class resolved, loudly, into the puntal's own `Options`: its turn runner and
stream observer then run the judge unchanged. A judge that cannot be run as configured must not
reach a backend, and the caller answers it as every pull request solo."""

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
from agent_os.product.puntal.constants import PATH_FAST, SUPPORTED_STREAM
from agent_os.product.puntal.options import Options
from agent_os.product.puntal.stream.events import Ceilings
from agent_os.product.puntal.stream.launch import backend_executable_for

INTEGRATOR_ROLE = "integrator"
# A safety against a hung process: the judge reads an index and answers one object.
TIMEOUT_SECONDS = 120


class JudgeRefused(Exception):
    """The judge cannot be run as configured. Raised before anything is spent."""


def run_dir_for(host_root: pathlib.Path) -> pathlib.Path:
    """`AGENT_CACHE_DIR` whole, as every role's driver reads it, else `.cache/integrator`."""
    override = os.environ.get("AGENT_CACHE_DIR")
    return pathlib.Path(override) if override else host_root / ".cache" / INTEGRATOR_ROLE


def backend_executable(backend: str, project) -> str:
    """`INTEGRATOR_<BACKEND>_BIN` (a test's override), else what the puntal resolves."""
    variable = "INTEGRATOR_" + "".join(c if c.isalnum() else "_" for c in backend.upper()) + "_BIN"
    return os.environ.get(variable) or backend_executable_for(backend, project)


def resolve_options(*, host_root: pathlib.Path, model: str | None = None) -> Options:
    try:
        config = load_agents_config()
        class_name, task_class = load_role_class(INTEGRATOR_ROLE)
        backend = backend_config(task_class.backend, project=config.project)
    except CONFIG_LOAD_ERRORS as error:
        raise JudgeRefused(config_load_failure(error)) from error
    except KeyError as error:
        raise JudgeRefused(str(error.args[0])) from error
    if backend.stream != SUPPORTED_STREAM:
        raise JudgeRefused(
            f"the integrator class runs on backend '{task_class.backend}', whose stream is "
            f"'{backend.stream}': its confinement here is the {SUPPORTED_STREAM} CLI's"
        )
    try:
        contract = render_prompt(
            INTEGRATOR_ROLE, {}, prompt_extras_path(INTEGRATOR_ROLE, config.project)
        )
    except (KeyError, FileNotFoundError) as error:
        raise JudgeRefused(str(error.args[0])) from error
    run_dir = run_dir_for(host_root)
    return Options(
        class_name=class_name,
        backend=task_class.backend,
        model=model or task_class.model,
        effort="",
        persistence_command="",
        executor_command="",
        read_subcommands=(),
        executor_timeout_seconds=0,
        ceilings=Ceilings(
            max_context=task_class.max_context,
            max_cost_usd=task_class.max_cost_usd,
            max_total_tokens=task_class.max_total_tokens,
            max_tool_calls=0,
            timeout_seconds=TIMEOUT_SECONDS,
        ),
        executable=backend_executable(task_class.backend, config.project),
        run_dir=run_dir,
        telemetry_file=run_dir / "telemetry.jsonl",
        host_root=host_root,
        fast_contract=contract,
        slow_contract="",
        path=PATH_FAST,
        plan_only=True,
    )
