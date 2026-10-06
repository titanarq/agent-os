"""The puntal's documentation says what the code does: the telemetry record is a contract, so the table
that documents it, the tuple that names it and the record the driver writes are held to one list, and
the decision record every comment points at exists.

Pure filesystem. This file must not request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import re

from agent_os.cli import AGENT_OS_DIR
from agent_os.product import puntal

DOCS = AGENT_OS_DIR / "docs"
ADR = (
    DOCS
    / "adr"
    / "2026-10-04-a-puntal-is-a-one-shot-headless-process-under-its-own-class-and-cannot-write-code.md"
)


def section_4_6() -> str:
    return (DOCS / "AGENT_OS.md").read_text().split("### 4.7", 1)[1].split("\n## ", 1)[0]


def test_every_telemetry_field_is_documented():
    section = section_4_6()
    missing = [name for name in puntal.TELEMETRY_FIELDS if f"`{name}`" not in section]
    assert not missing, f"docs/AGENT_OS.md section 4.7 does not document {missing}"


def test_every_latency_milestone_is_documented():
    section = section_4_6()
    milestones = [
        "total",
        "python_startup",
        "launch_overhead",
        "first_event",
        "first_message",
        "first_tool_call",
        "first_text_delta",
        "final_answer_first_delta",
        "backend_reported",
    ]
    assert not [m for m in milestones if m not in section]


def test_the_documented_exit_statuses_are_the_ones_the_driver_returns():
    section = section_4_6()
    for status in sorted(set(puntal.OUTCOME_EXIT_STATUS.values()) | {puntal.EXIT_NOT_RUN}):
        assert f"`{status}`" in section, status


def test_the_decision_record_exists_and_is_indexed_and_named_by_the_code_that_depends_on_it():
    assert ADR.is_file()
    assert ADR.name in (DOCS / "adr" / "README.md").read_text()
    assert (
        ADR.name.removesuffix(".md").replace("-and-", "-and-")
        in (DOCS / "CHANGELOG.md").read_text()
    )
    for path in ("agent_os/lib.py", "config.example.yaml", "docs/AGENT_OS.md"):
        text = (AGENT_OS_DIR / path).read_text()
        # Comments wrap a long ADR name across lines; compare with the wrapping taken out.
        flattened = re.sub(r"\s*\n\s*(#\s*)?", "", text)
        assert "a-puntal-is-a-one-shot-headless-process" in flattened, path


def test_the_schema_version_is_what_the_docs_say():
    assert f"`{puntal.TELEMETRY_SCHEMA}`" in section_4_6()
