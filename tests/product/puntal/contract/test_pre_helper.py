"""The pre-helper: what a node declares its action reads, loaded by code before the model runs.

Pure filesystem and subprocess (the app's persistence command is a tiny script). This file must not
request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json
import pathlib
import sys

from agent_os.product.puntal.fast.pre_helper import (
    load_declared_state,
    split_node_declaration,
)

NODE_BODY = "# Node UC-1\n\nDo the thing.\n"


def node_with(frontmatter: str) -> str:
    return f"---\n{frontmatter}\n---\n{NODE_BODY}"


def test_a_node_without_frontmatter_declares_nothing_and_is_the_slice_as_it_is():
    declaration = split_node_declaration(NODE_BODY)
    assert declaration.slice_text == NODE_BODY and declaration.reads == []
    assert declaration.problems == []


def test_the_reads_a_node_declares_are_taken_from_its_frontmatter_and_the_slice_loses_it():
    declaration = split_node_declaration(
        node_with("id: uc-1\nreads:\n  - list tickets\n  - get tickets {payload.id}")
    )
    assert declaration.reads == ["list tickets", "get tickets {payload.id}"]
    assert declaration.slice_text == NODE_BODY


def test_a_declaration_that_is_malformed_costs_the_fast_path_nothing_but_is_reported():
    for frontmatter in ("reads: list tickets", "reads: [1, 2]", "reads: [a: b"):
        declaration = split_node_declaration(node_with(frontmatter))
        assert declaration.reads == [] and declaration.problems, frontmatter


def test_frontmatter_that_is_not_a_mapping_is_left_in_the_text_untouched():
    text = "---\njust prose between rules\n---\nbody"
    declaration = split_node_declaration(text)
    assert declaration.slice_text == text and declaration.reads == []


STATE_SCRIPT = """\
import json, sys
words = sys.argv[1:]
if words[0] == "boom":
    print("store: broken", file=sys.stderr); sys.exit(1)
print(json.dumps({"called_with": words}))
"""


def persistence(tmp_path: pathlib.Path) -> list[str]:
    script = tmp_path / "state.py"
    script.write_text(STATE_SCRIPT)
    return [sys.executable, str(script)]


def load(tmp_path, reads, payload=None, allowed=("get", "list", "boom", "put")):
    return load_declared_state(
        reads,
        payload_text=json.dumps(payload) if payload is not None else "",
        persistence_command=persistence(tmp_path),
        allowed_subcommands=allowed,
        host_root=tmp_path,
        timeout_seconds=30,
    )


def test_each_declared_read_runs_through_the_persistence_command_and_lands_in_the_state_text(
    tmp_path,
):
    loaded = load(tmp_path, ["list tickets", "get tickets {payload.id}"], {"id": "T 1"})
    assert (loaded.declared, loaded.ran, loaded.failed) == (2, 2, 0)
    assert "## list tickets" in loaded.text and '"called_with": ["list", "tickets"]' in loaded.text
    # A payload value is ONE argument whatever it contains: no shell ever sees it.
    assert '["get", "tickets", "T 1"]' in loaded.text
    assert loaded.duration_s >= 0


def test_the_state_text_keeps_the_declaration_order_whatever_order_the_reads_finish_in(tmp_path):
    loaded = load(tmp_path, [f"get c{n}" for n in range(8)])
    assert [line for line in loaded.text.splitlines() if line.startswith("## ")] == [
        f"## get c{n}" for n in range(8)
    ]


def test_a_read_that_fails_is_shown_to_the_model_as_what_the_app_said_not_hidden(tmp_path):
    loaded = load(tmp_path, ["boom x"])
    assert (loaded.ran, loaded.failed) == (1, 1)
    assert "failed (exit status 1)" in loaded.text and "store: broken" in loaded.text


def test_a_read_that_cannot_be_formed_is_skipped_and_reported_never_guessed(tmp_path):
    loaded = load(
        tmp_path,
        ["get tickets {payload.id}", "put tickets T-1 {}", "   "],
        {"x": 1},
        allowed=("get", "list"),
    )
    assert loaded.ran == 0 and loaded.failed == 3
    assert "## put tickets T-1 {}\nskipped" in loaded.text
    joined = " | ".join(loaded.problems)
    assert "payload has no 'id'" in joined
    assert "'put' is not a read" in joined


def test_a_payload_that_is_not_json_only_breaks_the_reads_that_need_it(tmp_path):
    loaded = load_declared_state(
        ["list tickets", "get tickets {payload.id}"],
        payload_text="plain words",
        persistence_command=persistence(tmp_path),
        allowed_subcommands=("get", "list"),
        host_root=tmp_path,
        timeout_seconds=30,
    )
    assert (loaded.ran, loaded.failed) == (1, 1)


def test_an_output_past_the_cap_is_cut_and_says_so(tmp_path):
    script = tmp_path / "big.py"
    script.write_text("print('x' * 100000)")
    loaded = load_declared_state(
        ["list tickets"],
        payload_text="",
        persistence_command=[sys.executable, str(script)],
        allowed_subcommands=("list",),
        host_root=tmp_path,
        timeout_seconds=30,
    )
    assert len(loaded.text) < 25000 and "cut at" in loaded.text


def test_a_nested_payload_field_can_be_named_with_dots(tmp_path):
    loaded = load(tmp_path, ["get tickets {payload.ticket.id}"], {"ticket": {"id": "T-5"}})
    assert '["get", "tickets", "T-5"]' in loaded.text


def test_a_skipped_read_keeps_its_place_among_the_ones_that_ran(tmp_path):
    loaded = load(tmp_path, ["get a", "put b", "get c"], allowed=("get",))
    assert [line for line in loaded.text.splitlines() if line.startswith("## ")] == [
        "## get a",
        "## put b",
        "## get c",
    ]


def test_a_node_slice_that_opens_with_a_dash_cannot_be_read_by_the_cli_as_an_option():
    from agent_os.product.puntal.fast.brief import build_brief

    brief = build_brief(node_slice="---\nstray\n", action="a", payload="", relevant_state="")
    assert not brief.startswith("-") and "stray" in brief
