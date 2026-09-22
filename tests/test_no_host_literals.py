"""`agent_os/` carries no literal of any host project (docs/AGENT_OS.md's own agnosticism claim,
`docs/adr/2026-09-14-the-agent-mechanism-is-project-agnostic-and-configured-not-coded.md`).

A blunt substring walk over every file under `agent_os/`, excluding `docs/` (history and the
module doc are allowed to name the projects they were written about), `tests/golden/` (fixture
data captured from a real run, not code) and `config.example.yaml` (its own commentary explains
the shape of a real value by naming one, `docs/AGENT_OS.md` §4.1). #510's own audit found files
that still fail this walk and belong to a sibling wave-2 issue, #512, running in parallel --
excluded by name below rather than fixed here, so the PR that lands #512 also shrinks
`EXCLUDED_PATHS` (the driver-side half of the same audit, #509, is already clean: it merged first
and this walk was written against its result):

- `agent_os/tests/test_agent_guard.py`, `test_agent_lib.py`, `test_agent_task.py`,
  `test_issues_cli.py`, `test_prompt_templates.py`, `test_role_run_environment_isolation.py`,
  `test_worker_task.py` -- fixtures and assertions pinned to this project's own values, and one
  `importorskip("roedor.config")` (the parent epic's own 2026-09-21 audit, #512).

Pure filesystem. This file must not request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import pathlib

from agent_os.cli import AGENT_OS_DIR

FORBIDDEN = ("roedor", "MatillaM", "titanarq", "5435", "roedor_ro")

# This file's own path, relative to `agent_os/` -- it necessarily spells every forbidden literal
# to check for it, so it is excluded by identity rather than added to `EXCLUDED_PATHS`, which is
# reserved for files a SIBLING issue still needs to fix.
_SELF = pathlib.Path(__file__).resolve().relative_to(AGENT_OS_DIR).as_posix()

# Paths relative to `agent_os/`, owned by #512 and not fixed here -- see the module docstring
# above. `test_every_exclusion_still_applies` below keeps this list honest: an entry the walk no
# longer needs fails that test instead of quietly shrinking what the walk actually checks.
EXCLUDED_PATHS = {
    "tests/test_agent_guard.py",
    "tests/test_agent_lib.py",
    "tests/test_agent_task.py",
    "tests/test_issues_cli.py",
    "tests/test_prompt_templates.py",
    "tests/test_role_run_environment_isolation.py",
    "tests/test_worker_task.py",
}


def _is_excluded_by_location(relative_parts: tuple[str, ...]) -> bool:
    if relative_parts[0] in (".venv", "__pycache__"):
        return True
    if relative_parts[0] == "docs":
        return True
    if "tests" in relative_parts and "golden" in relative_parts:
        return True
    return relative_parts[-1] == "config.example.yaml"


def _files():
    """Every real file under `agent_os/` not excluded by its LOCATION -- `EXCLUDED_PATHS` is
    checked separately by each test below, not folded in here, so the second test can still see
    the files the first one skips."""
    for path in sorted(AGENT_OS_DIR.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(AGENT_OS_DIR)
        if _is_excluded_by_location(relative.parts) or relative.as_posix() == _SELF:
            continue
        yield path, relative.as_posix()


def _literals_in(path):
    try:
        text = path.read_text(errors="strict")
    except (UnicodeDecodeError, OSError):
        return []
    return [literal for literal in FORBIDDEN if literal in text]


def test_no_host_literal_anywhere_under_agent_os():
    violations = [
        f"{relative}: {found}"
        for path, relative in _files()
        if relative not in EXCLUDED_PATHS
        for found in _literals_in(path)
    ]
    assert not violations, "host literal(s) found:\n" + "\n".join(violations)


def test_every_exclusion_still_applies():
    # An exclusion this list carries but the walk no longer needs is a silent regression: the
    # sibling issue's own fix landed, the entry was not removed with it, and the walk has quietly
    # been checking less than `EXCLUDED_PATHS` claims ever since.
    by_relative = {relative: path for path, relative in _files()}
    stale = [
        relative
        for relative in EXCLUDED_PATHS
        if relative in by_relative and not _literals_in(by_relative[relative])
    ]
    assert not stale, f"exclusion(s) no longer needed, remove from EXCLUDED_PATHS: {stale}"
    missing = [relative for relative in EXCLUDED_PATHS if relative not in by_relative]
    assert not missing, f"exclusion(s) naming a file that no longer exists: {missing}"
