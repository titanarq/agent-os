"""Generic `__TOKEN__` substitution for the mechanism's own prompt templates
(`agent_os/agents/*.md`, #510), so `agent_os.install` renders them the same way whatever the
templates turn out to name inside them -- this module owns the mapping from a token's NAME to a
`config/agents.yaml` value, never a template's own text.

The token vocabulary is fixed by #510's templates, not invented here: `__GUARD_UNIT__`,
`__WORKTREES__`, `__HUMAN_LOGIN__`, `__TEST_COMMAND__`, `__MODULE_DOCS__`, `__MECHANISM_DIR__`, and, for the control
plane's REST merge step (agent-os#88), `__REPO__` and `__MERGE_METHOD__`, and, for each definition's `model:` frontmatter (agent-os#96),
`__CONTROL_PLANE_MODEL__`, `__WORKER_RUNNER_MODEL__` and `__TASK_WRITER_MODEL__`. A template naming a
token outside that set is refused after substitution -- whatever is left over that still looks
like a token (`__[A-Z][A-Z0-9_]*__`) is an unknown one, because every known token has already been
replaced by then, so what remains is either a typo in the template or a token this renderer has
not been taught yet, and either way rendering it silently would leave a literal `__SOMETHING__` in
a prompt a human is meant to trust.
"""

from __future__ import annotations

import re

from agent_os.lib import ProjectConfig

UNKNOWN_TOKEN_RE = re.compile(r"__[A-Z][A-Z0-9_]*__")

# Where a host keeps the mechanism, relative to its root: the `git subtree` prefix every host is
# told to pull into (docs/adoption/substrate.md step 7). The commands an agent definition names are spelled
# from it because it is the one path every host has -- a `scripts/` wrapper is a host's own choice,
# and a host that wrote none was sent to files that do not exist.
MECHANISM_DIR = "agent_os"


class RenderError(Exception):
    """A template still carries a token after every known one was substituted."""


def render_worktrees(project: ProjectConfig) -> str:
    """`qwen: ../example-qwen, claude: ../example-claude` -- one `backend: path` pair per
    `project.backends` entry that has a worktree, in the order `config/agents.yaml` declares them."""
    return ", ".join(
        f"{name}: {backend.worktree}"
        for name, backend in project.backends.items()
        if backend.worktree
    )


def token_values(project: ProjectConfig) -> dict[str, str]:
    """Every token this renderer knows, and the `project:` value it stands for. Adding a token
    the templates need is a one-line change here, never a special case in `render_agent_template`
    itself."""
    return {
        "__GUARD_UNIT__": project.guard_unit,
        "__WORKTREES__": render_worktrees(project),
        "__HUMAN_LOGIN__": project.human_login,
        "__TEST_COMMAND__": project.test_command,
        "__MODULE_DOCS__": project.module_docs_dir,
        "__MECHANISM_DIR__": MECHANISM_DIR,
        "__REPO__": project.repo,
        "__MERGE_METHOD__": project.merge_method,
        "__CONTROL_PLANE_MODEL__": project.agent_models.control_plane,
        "__WORKER_RUNNER_MODEL__": project.agent_models.worker_runner,
        "__TASK_WRITER_MODEL__": project.agent_models.task_writer,
    }


def render_agent_template(template: str, project: ProjectConfig) -> str:
    rendered = template
    for token, value in token_values(project).items():
        rendered = rendered.replace(token, value)
    leftover = UNKNOWN_TOKEN_RE.findall(rendered)
    if leftover:
        raise RenderError(f"unknown token(s) left in the rendered output: {leftover}")
    return rendered
