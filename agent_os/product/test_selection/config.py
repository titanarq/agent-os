"""The `project.test_selection` section of a host's `config/agents.yaml`. It imports nothing from
`agent_os.lib` because `lib` imports it to declare the section."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TestSelectionConfig(BaseModel):
    __test__ = False  # not a pytest class, whatever its name starts with
    model_config = ConfigDict(extra="forbid")

    # The manifest file, or the folder of manifest files, relative to the repository root. Empty
    # means selection is off: every plan is the whole suite and nothing changes for the host.
    manifest: str = ""
