"""Whether the interpreter that runs the mechanism imports what `agent_os.product` needs, and the
one line that says how to repair it when it does not.

The dependencies (`pyyaml`, `pydantic`, `PyJWT[crypto]`) are declared once, in `pyproject.toml`,
and installed only by `bootstrap.sh` into the mechanism's own `.venv`
(`docs/adr/2026-09-21-the-mechanism-is-one-directory-extended-by-hosts-and-never-modified.md`). A
host's root `.venv` is the host's own, carries the host's packages and is never expected to import
`agent_os`: a command of the mechanism run on it fails with a bare `No module named 'pydantic'`
that does not say which interpreter it wanted. The doctor probes the right one before the first
command (`docs/adoption/substrate.md` step 16), and again after a `git subtree pull` that may have
added a dependency to a `.venv` nobody rebuilt (step 25).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from agent_os.cli import AGENT_OS_DIR, agent_os_python

# Third-party distributions as `pyproject.toml` declares them (`cryptography` is what the
# `PyJWT[crypto]` extra brings: without it the GitHub App JWT has no RS256 signer), then the
# module that reaches every one of the product's own imports.
PROBED_MODULES = ("yaml", "pydantic", "jwt", "cryptography", "agent_os.product.sessions.cli")
PROBE_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class InterpreterVerdict:
    python: str
    problem: str | None

    @property
    def ok(self) -> bool:
        return self.problem is None


def repair_command(python: str) -> str:
    """The exact command that makes `python` import the mechanism: `bootstrap.sh` for the
    interpreter it builds, an editable install for one the host named in `$AGENT_OS_PYTHON`."""
    if os.environ.get("AGENT_OS_PYTHON"):
        return f"{python} -m pip install -e {AGENT_OS_DIR}"
    return f"bash {AGENT_OS_DIR / 'bootstrap.sh'}"


def intended_interpreter(python: str) -> str:
    """Where the mechanism's commands are meant to run: the interpreter `$AGENT_OS_PYTHON` names,
    else the `.venv` `bootstrap.sh` builds beside the package."""
    if os.environ.get("AGENT_OS_PYTHON"):
        return python
    return str(AGENT_OS_DIR / ".venv" / "bin" / "python")


def probe_mechanism_interpreter(python: str | None = None) -> InterpreterVerdict:
    """Runs `python -c "import yaml, pydantic, ..."` in the environment a role would run with
    (`$PYTHONPATH` included: a run in a worktree reaches the package through it) and names the
    first import that fails. Read-only."""
    python = python or agent_os_python()
    import_statement = "import " + ", ".join(PROBED_MODULES)
    try:
        result = subprocess.run(
            [python, "-c", import_statement],
            capture_output=True,
            text=True,
            check=False,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as failure:
        return InterpreterVerdict(python, f"cannot run it ({failure})")
    if result.returncode == 0:
        return InterpreterVerdict(python, None)
    reason = (result.stderr.strip().splitlines() or [f"exited {result.returncode}"])[-1]
    return InterpreterVerdict(python, reason)


def describe_mechanism_interpreter(verdict: InterpreterVerdict) -> str:
    """The doctor's detail line: the interpreter that passed, or what it lacks and the command that
    fixes it, with the reminder of which interpreter the mechanism's commands belong to."""
    if verdict.ok:
        return f"{verdict.python} imports {', '.join(PROBED_MODULES)}"
    not_the_root_venv = "" if os.environ.get("AGENT_OS_PYTHON") else ", not on a host's root .venv"
    return (
        f"{verdict.python}: {verdict.problem} -- the mechanism's commands (`agent-os-*`, "
        f"`python -m agent_os...`) run on {intended_interpreter(verdict.python)}"
        f"{not_the_root_venv}; repair it with `{repair_command(verdict.python)}` "
        "(docs/adoption/substrate.md step 16)"
    )
