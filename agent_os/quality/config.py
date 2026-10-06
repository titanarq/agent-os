"""The `quality:` section of a host's `config/agents.yaml`: the limits the code-quality ratchet
enforces and the paths it does not look at. It imports nothing from `agent_os.lib` because `lib`
imports it to declare the section, and a cycle there would make the section unloadable."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_MAX_ENTRIES_PER_FOLDER = 12
DEFAULT_MAX_LINES_PER_FILE = 300

# Paths that hold prose or recorded data and not code, so a line or entry limit says nothing about
# them: a changelog only ever grows, and a golden fixture is a recording of a rendered prompt.
# The host's product tree is excluded as well, from the `tree.root` key, and so is a mechanism
# directory vendored under the host (`agent_os/` is read-only there).
DEFAULT_EXCLUDED_PATHS: tuple[str, ...] = (
    "docs/",
    "tests/golden/",
    "config.example.yaml",
    "uv.lock",
)


class QualityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_entries_per_folder: int = Field(default=DEFAULT_MAX_ENTRIES_PER_FOLDER, ge=1)
    max_lines_per_file: int = Field(default=DEFAULT_MAX_LINES_PER_FILE, ge=1)
    excluded_paths: list[str] = list(DEFAULT_EXCLUDED_PATHS)
