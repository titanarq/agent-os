"""`depends_on`: a list of node ids the doctor checks exist and do not loop. Filesystem only."""

from __future__ import annotations

import pathlib

from tree_helpers import write_node, write_sound_tree

from agent_os.product.tree.checks import check_tree
from agent_os.product.tree.loader import load_tree


def found(root: pathlib.Path) -> list[tuple[str, str]]:
    return [(defect.path.name, defect.code) for defect in check_tree(load_tree(root))]


def test_a_dependency_on_an_existing_node_is_sound(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-base", "use-case", parent="fr-offline")
    write_node(tmp_path, "uc-edit", "use-case", parent="fr-offline", depends_on=["uc-base"])
    assert found(tmp_path) == []


def test_a_dependency_on_nothing_is_dangling(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-edit", "use-case", parent="fr-offline", depends_on=["uc-ghost"])
    assert found(tmp_path) == [("uc-edit.md", "dangling-dependency")]


def test_a_dependency_on_a_decision_is_dangling_and_says_so(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-edit", "use-case", parent="fr-offline", depends_on=["dec-local-first"])
    (defect,) = check_tree(load_tree(tmp_path))
    assert defect.code == "dangling-dependency" and "decision" in defect.message


def test_a_dependency_that_failed_to_load_is_not_also_dangling(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-broken", "use-case", parent="fr-offline", mechanism=None)
    write_node(tmp_path, "uc-edit", "use-case", parent="fr-offline", depends_on=["uc-broken"])
    assert ("uc-edit.md", "dangling-dependency") not in found(tmp_path)


def test_a_node_cannot_depend_on_itself(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-edit", "use-case", parent="fr-offline", depends_on=["uc-edit"])
    assert found(tmp_path) == [("uc-edit.md", "dependency-cycle")]


def test_a_dependency_cycle_is_reported_on_every_member_and_only_on_them(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-a", "use-case", parent="fr-offline", depends_on=["uc-b"])
    write_node(tmp_path, "uc-b", "use-case", parent="fr-offline", depends_on=["uc-c"])
    write_node(tmp_path, "uc-c", "use-case", parent="fr-offline", depends_on=["uc-a", "uc-edit"])
    assert sorted(found(tmp_path)) == [
        ("uc-a.md", "dependency-cycle"),
        ("uc-b.md", "dependency-cycle"),
        ("uc-c.md", "dependency-cycle"),
    ]


def test_a_diamond_is_not_a_cycle(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-base", "use-case", parent="fr-offline")
    write_node(tmp_path, "uc-left", "use-case", parent="fr-offline", depends_on=["uc-base"])
    write_node(tmp_path, "uc-right", "use-case", parent="fr-offline", depends_on=["uc-base"])
    write_node(
        tmp_path, "uc-top", "use-case", parent="fr-offline", depends_on=["uc-left", "uc-right"]
    )
    assert found(tmp_path) == []


def test_a_dependency_listed_twice_is_a_schema_error(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path, "uc-edit", "use-case", parent="fr-offline", depends_on=["uc-edit", "uc-edit"]
    )
    assert ("uc-edit.md", "schema") in found(tmp_path)
