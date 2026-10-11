"""The `project.test_selection` section of a host's `config/agents.yaml`. It imports nothing from
`agent_os.lib` because `lib` imports it to declare the section."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TestSelectionConfig(BaseModel):
    __test__ = False  # not a pytest class, whatever its name starts with
    model_config = ConfigDict(extra="forbid")

    # The manifest file, or the folder of manifest files, relative to the repository root. Empty
    # means selection is off: every plan is the whole suite and nothing changes for the host.
    manifest: str = ""

    # Hours after which a pull request's CI runs the whole suite again, however little it
    # touched. The clock is the age of the last successful full run, read from GitHub Actions.
    full_run_interval_hours: int = Field(default=4, gt=0)
