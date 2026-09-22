"""`agent_os/prompts/` and `agent_os.lib.render_prompt` -- where every role's prompt lives now, and
the proof that moving it out of the drivers' heredocs changed nothing an agent reads.

The golden test below renders all four prompts through the HOST project's real
`config/agents.yaml` and compares them with `agent_os/tests/golden/`, captured from the same
drivers before the move (#509). It is the one test in this file that reads the host's config, and
it reads it through `capture_golden.sh`, which resolves the host root from the package's own
location rather than from a cwd. #512 moves host-config-reading assertions into the host's own
conformance tests; if that happens, this one goes with them and the rest of the file stays.

Pure filesystem and subprocess: nothing here launches a backend, mints an identity or touches a
database.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from agent_os.cli import AGENT_OS_DIR
from agent_os.lib import (
    PROJECT_EXTRAS_PLACEHOLDER,
    PROMPT_ROLES,
    PROMPTS_DIR,
    prompt_extras_path,
    render_prompt,
)

CAPTURE = AGENT_OS_DIR / "tests" / "capture_golden.sh"
GOLDEN_DIR = AGENT_OS_DIR / "tests" / "golden"


def _words(text: str) -> list[str]:
    """The prompt with every run of whitespace reduced to one break: what the golden comparison is
    about is the words an agent reads and their order, never where a rendered paragraph happened to
    be re-wrapped or which line a substituted block landed on."""
    return text.split()


@pytest.fixture(scope="module")
def captured(tmp_path_factory) -> pathlib.Path:
    """Every role's prompt as its own driver resolves it today, into a directory of its own."""
    out = tmp_path_factory.mktemp("captured-prompts")
    result = subprocess.run(
        ["bash", str(CAPTURE), str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return out


@pytest.mark.parametrize("role", PROMPT_ROLES)
def test_the_role_renders_exactly_what_it_rendered_before_the_templates_existed(role, captured):
    """The whole point of #509: the prompt text moved out of three shell heredocs into four files
    and an extension point the host fills, and what reaches a backend is word for word what reached
    it before. A difference here is either a wording change nobody asked for or a placeholder that
    stopped being substituted."""
    rendered = (captured / f"{role}.md").read_text()
    golden = (GOLDEN_DIR / f"{role}.md").read_text()
    assert _words(rendered) == _words(golden)


@pytest.mark.parametrize("role", PROMPT_ROLES)
def test_every_template_carries_the_hosts_extension_point(role):
    """One marked place per role where a host's own paragraphs go. Without it a host has nowhere to
    put a sentence only it can write, and the sentence goes back into the mechanism's own text --
    which is the defect `docs/AGENT_OS.md` §7 row (t) recorded."""
    assert PROJECT_EXTRAS_PLACEHOLDER in (PROMPTS_DIR / f"{role}.md").read_text()


def test_a_role_whose_host_names_no_extras_renders_no_gap_where_they_would_go():
    """An empty extension point takes its own line with it, and one of the two blank lines that
    fenced it -- never both, and never a heading with nothing under it. The same rule every other
    paragraph rendered from config has followed since #363."""
    rendered = render_prompt(
        "worker",
        {
            "HUMAN_LOGIN": "someone",
            "HUMAN_MESSAGE_RULES": "WRITING TO THE HUMAN\nin their language.",
            "TEST_COMMAND": "make test",
            "MAIN_CHECKOUT": "/somewhere",
            "FORBIDDEN_PATHS_RULES": "",
            "MECHANISM_PATHS_RULES": "",
            "NEVER_RUN_RULES": "",
            "WORKER_ENVIRONMENT_RULES": "",
        },
    )
    assert PROJECT_EXTRAS_PLACEHOLDER not in rendered
    assert "\n\n\n" not in rendered


def test_a_hosts_own_paragraph_reaches_the_prompt_and_is_substituted_like_the_text_around_it(
    tmp_path,
):
    """The extras are inserted BEFORE the placeholders are filled, so a host paragraph may use the
    mechanism's own placeholders instead of repeating a value the config already holds -- which is
    what roedor's own worker file does with `__TEST_COMMAND__`."""
    extras = tmp_path / "worker.md"
    extras.write_text("HOW THIS PROJECT RUNS ITS TESTS\n- `bash __TEST_COMMAND__ <paths>`.\n")
    rendered = render_prompt(
        "worker",
        {
            "HUMAN_LOGIN": "someone",
            "HUMAN_MESSAGE_RULES": "WRITING TO THE HUMAN\nin their language.",
            "TEST_COMMAND": "make test",
            "MAIN_CHECKOUT": "/somewhere",
            "FORBIDDEN_PATHS_RULES": "",
            "MECHANISM_PATHS_RULES": "",
            "NEVER_RUN_RULES": "",
            "WORKER_ENVIRONMENT_RULES": "",
        },
        extras,
    )
    assert "HOW THIS PROJECT RUNS ITS TESTS" in rendered
    assert "`bash make test <paths>`" in rendered


def test_the_renderer_refuses_an_extras_file_the_config_names_and_the_filesystem_lacks(tmp_path):
    """A host that names a file and then moves it must hear about it. Rendering the paragraph away
    silently would leave a prompt that is merely shorter, and nothing downstream could tell that
    from a host which configured none."""
    with pytest.raises(FileNotFoundError):
        render_prompt("worker", {}, tmp_path / "never-written.md")


def test_the_renderer_refuses_a_placeholder_nothing_answered():
    """A prompt is a contract, and `__WORKTREE__` reaching an agent as those nine characters is a
    clause it cannot act on. The refusal is what stops a driver before it launches a backend."""
    with pytest.raises(KeyError) as failure:
        render_prompt("validator", {})
    assert "__WORKTREE__" in str(failure.value)


def test_an_unknown_role_has_no_template_and_says_so():
    with pytest.raises(KeyError):
        render_prompt("archivist", {})


def test_the_host_of_this_checkout_names_the_two_files_its_prompts_need():
    """roedor's own half of #509: the two paragraphs that used to be literals inside the mechanism
    are files this project owns, and `project.prompt_extras` names both. This is the one assertion
    here about the HOST rather than the mechanism -- #512's place, if it moves."""
    for role in ("worker", "refiner"):
        path = prompt_extras_path(role)
        assert path is not None, f"config/agents.yaml names no prompt_extras for the {role}"
        assert path.is_file(), path
