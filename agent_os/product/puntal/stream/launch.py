"""Launching the backend: the confining flags, the shim, the process and its watchdog."""

from __future__ import annotations

import contextlib
import dataclasses
import os
import pathlib
import shlex
import signal
import subprocess
import threading
import time

from agent_os.lib import ProjectConfig, backend_executable
from agent_os.product.puntal.constants import (
    ALLOW_RULE,
    PERSISTENCE_TOOL,
    SHIM_NAME,
    TERMINATION_GRACE_SECONDS,
)
from agent_os.product.puntal.stream.observer import StreamObserver


class Clock:
    """Seconds since `puntal_task.sh` was entered. The shell exports the epoch second it started at
    (`PUNTAL_LAUNCH_EPOCH`), so the interpreter's own start-up and the config load are inside every
    latency instead of invisible to it -- they are part of what the person clicking waits for."""

    def __init__(self, launch_epoch: float | None) -> None:
        self._started = time.monotonic()
        self.overhead_before_python_s = (
            max(0.0, time.time() - launch_epoch) if launch_epoch is not None else 0.0
        )

    def now(self) -> float:
        return self.overhead_before_python_s + (time.monotonic() - self._started)


def backend_flags(
    *, model: str, effort: str, max_cost_usd: float, with_state_tool: bool = True
) -> list[str]:
    """The `claude` command-line flags that confine a puntal, in the order the CLI reads them. The
    options that take a list of values are written `--name=value`: a variadic option followed by a
    space swallows every following argument, the prompt among them.

    `with_state_tool` is the slow path's: the one Bash rule that lets `./state` run. The fast path
    offers no tool at all (`--tools=` is the CLI's way to say so), and no rule to allow one."""
    tool_flags = (
        [f"--tools={PERSISTENCE_TOOL}", f"--allowedTools={ALLOW_RULE}"]
        if with_state_tool
        else ["--tools="]
    )
    flags = [
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--safe-mode",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        *tool_flags,
        "--max-budget-usd",
        f"{max_cost_usd:g}",
        "--model",
        model,
    ]
    if effort:
        flags += ["--effort", effort]
    return flags


def backend_executable_for(backend: str, project: ProjectConfig) -> str:
    """`PUNTAL_<BACKEND>_BIN` -- a test's or a bench's override, derived from the name like the other
    drivers' -- else the configured command, else the bare name."""
    variable = "PUNTAL_" + "".join(c if c.isalnum() else "_" for c in backend.upper()) + "_BIN"
    return os.environ.get(variable) or backend_executable(backend, project=project)


def write_state_shim(scratch: pathlib.Path, host_root: pathlib.Path, argv: list[str]) -> None:
    """The puntal's whole tool: `./state ...` in the scratch directory, which runs the app's
    persistence command from the host's root with the arguments it was given."""
    command = list(argv)
    if "/" in command[0] and not os.path.isabs(command[0]):
        command[0] = str(host_root / command[0])
    shim = scratch / SHIM_NAME
    shim.write_text(
        "#!/bin/sh\n"
        f"cd {shlex.quote(str(host_root))} || exit 1\n"
        f'exec {" ".join(shlex.quote(part) for part in command)} "$@"\n'
    )
    shim.chmod(0o755)


@dataclasses.dataclass
class BackendRun:
    exit_code: int | None
    cut: tuple[str, str] | None
    timed_out: bool


def _kill_process_group(process: subprocess.Popen, *, grace: float) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)


def run_backend(
    argv: list[str],
    *,
    cwd: pathlib.Path,
    environment: dict[str, str],
    observer: StreamObserver,
    clock: Clock,
    log,
    timeout_seconds: int,
) -> BackendRun:
    """Starts the backend in its own session, folds its stdout into `observer` as it arrives and
    appends every raw line to `log`. The timeout is a watchdog on the whole process group, the one
    safety against a hung process; a cut the observer asks for ends the run as soon as it is seen."""
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    timed_out = threading.Event()

    def on_timeout() -> None:
        timed_out.set()
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)

    watchdog = threading.Timer(timeout_seconds, on_timeout)
    watchdog.daemon = True
    watchdog.start()
    cut: tuple[str, str] | None = None
    try:
        for line in iter(process.stdout.readline, ""):
            at_s = clock.now()
            log.write(line if line.endswith("\n") else line + "\n")
            log.flush()
            cut = observer.observe_line(line, at_s)
            if cut is not None:
                _kill_process_group(process, grace=TERMINATION_GRACE_SECONDS)
                break
        process.wait()
    finally:
        watchdog.cancel()
        if process.poll() is None:
            _kill_process_group(process, grace=0.0)
        process.stdout.close()
    return BackendRun(process.returncode, cut, timed_out.is_set())
