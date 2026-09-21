"""The mechanism's own fixtures, and nothing of any host project.

It is a separate file from the host's `tests/conftest.py` on purpose (#508): that one imports the
host's database layer at module scope, which a suite meant to run in a project with no database
cannot do. Nothing here touches a network, a database or a real backend, so
`agent_os/.venv/bin/pytest agent_os/tests -q` is the whole run.

The helper below is imported by name (`from conftest import config_with_never_run`): pytest puts
this directory on `sys.path` for its own collection, so the module is reachable as `conftest`.
"""

from __future__ import annotations

import pathlib
import re

from agent_os.cli import AGENT_OS_DIR

# The HOST project whose `config/agents.yaml` the helper patches: the directory the package sits in.
HOST_ROOT = AGENT_OS_DIR.parent


def config_with_never_run(tmp_path, items):
    """A copy of the real config/agents.yaml with `project.never_run` replaced by `items` --
    (command, reason) pairs, or nothing at all for an empty list -- written under `tmp_path` and
    returned as a path. The drivers pick it up through `AGENTS_CONFIG_PATH`, which is how a test
    renders the three RULES blocks from a list this repository does not ship, and from an empty one
    (`docs/AGENT_OS.md` §7 row (b), issue #363). Shared by `test_worker_task.py` and
    `test_agent_task.py` because the point of the list is that all three blocks read it."""
    text = (HOST_ROOT / "config" / "agents.yaml").read_text()
    block = (
        "  never_run: []\n"
        if not items
        else "  never_run:\n"
        + "".join(
            f'    - command: "{command}"\n      reason: "{reason}"\n' for command, reason in items
        )
    )
    patched, count = re.subn(
        r"^  never_run:\n(?:    .*\n)+",
        # A callable rather than the string itself: `re.subn` would read a backslash inside a
        # reason as one of its own escapes.
        lambda _match: block,
        text,
        count=1,
        flags=re.MULTILINE,
    )
    assert count == 1, "config/agents.yaml's project.never_run block changed shape"
    path = pathlib.Path(tmp_path) / "agents.yaml"
    path.write_text(patched)
    return path
