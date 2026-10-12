"""The two classes of the consolidation resolved, loudly, into the puntal's own `Options`, so its turn
runner and stream observer run the drafter and the reviewer unchanged. Sonnet drafts and Opus reviews
because the host's `config/agents.yaml` says so on two classes, never because this file does
(`docs/adr/2026-10-12-a-use-case-that-an-amendment-contradicts-is-consolidated-into-one-definition.md`)."""

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

DRAFTER_ROLE = "consolidator"
REVIEWER_ROLE = "consolidation_reviewer"
# Both prompts live in `prompts/consolidation/`, which keeps `prompts/` under its entry limit.
PROMPT_OF_ROLE = {DRAFTER_ROLE: "consolidator", REVIEWER_ROLE: "reviewer"}
# A safety against a hung process: the drafter writes a whole use case in one turn.
TIMEOUT_SECONDS = 600


class ConsolidationRefused(Exception):
    """The consolidation cannot be run as configured. Raised before anything is spent."""


def run_directory_for(host_root: pathlib.Path) -> pathlib.Path:
    """`AGENT_CACHE_DIR` whole, as every role's driver reads it, else `.cache/consolidator`."""
    override = os.environ.get("AGENT_CACHE_DIR")
    return pathlib.Path(override) if override else host_root / ".cache" / DRAFTER_ROLE


def backend_executable(role: str, backend: str, project) -> str:
    """`<ROLE>_<BACKEND>_BIN` (a test's override), else what the puntal resolves."""
    spelled = "".join(c if c.isalnum() else "_" for c in f"{role}_{backend}".upper())
    return os.environ.get(f"{spelled}_BIN") or backend_executable_for(backend, project)


def resolve_options(role: str, *, host_root: pathlib.Path) -> Options:
    try:
        config = load_agents_config()
        class_name, task_class = load_role_class(role)
        backend = backend_config(task_class.backend, project=config.project)
    except CONFIG_LOAD_ERRORS as error:
        raise ConsolidationRefused(config_load_failure(error)) from error
    except KeyError as error:
        raise ConsolidationRefused(str(error.args[0])) from error
    if backend.stream != SUPPORTED_STREAM:
        raise ConsolidationRefused(
            f"the {role} class runs on backend '{task_class.backend}', whose stream is "
            f"'{backend.stream}': its confinement here is the {SUPPORTED_STREAM} CLI's"
        )
    try:
        contract = render_prompt(
            f"consolidation/{PROMPT_OF_ROLE[role]}", {}, prompt_extras_path(role, config.project)
        )
    except (KeyError, FileNotFoundError) as error:
        raise ConsolidationRefused(str(error.args[0])) from error
    run_dir = run_directory_for(host_root)
    return Options(
        class_name=class_name,
        backend=task_class.backend,
        model=task_class.model,
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
        executable=backend_executable(role, task_class.backend, config.project),
        run_dir=run_dir,
        telemetry_file=run_dir / "telemetry.jsonl",
        host_root=host_root,
        fast_contract=contract,
        slow_contract="",
        path=PATH_FAST,
        plan_only=True,
    )
