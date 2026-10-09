"""What a node points at, which the doctor checks: the nodes in `depends_on` exist and do not loop,
and the paths of a built node's `implementation` still exist in the repository. Filesystem and a
throwaway git repository only."""

from __future__ import annotations

import pathlib
import subprocess

from tree_helpers import write_node, write_sound_tree

from agent_os.product.tree import cli
from agent_os.product.tree.checks import CHECKS, check_tree
from agent_os.product.tree.loader import load_tree
from agent_os.product.tree.reference_checks import (
    IMPLEMENTATION_PATH_MISSING,
    repository_root_of,
)


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


# --------------------------------------------------------------------------------------------
# `implementation` paths: a built node whose pointer went stale
# --------------------------------------------------------------------------------------------


def repository_with_a_tree(tmp_path, **files) -> pathlib.Path:
    """A git repository with the files given (path -> content) and a sound tree under `product/`;
    returns the tree root."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name, content in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(content)
    tree_root = tmp_path / "product"
    write_sound_tree(tree_root)
    return tree_root


def doctor_of_the_repository(tree_root):
    tree = load_tree(tree_root)
    return [
        (defect.path.name, defect.code, defect.message)
        for defect in check_tree(tree, repository_root_of(tree_root))
    ]


def built_node(tree_root, implementation, state="implemented"):
    write_node(
        tree_root,
        "uc-sync",
        "use-case",
        parent="fr-offline",
        state=state,
        mechanism="a queue",
        implementation=implementation,
    )


def test_a_pointer_to_a_file_that_was_deleted_is_reported_with_the_path(tmp_path):
    tree_root = repository_with_a_tree(tmp_path, **{"web/app/ui/pages.py": "x\n"})
    built_node(tree_root, "web/app/ui/pages.py y web/app/ui/templates/entry.html, que se quitan")
    assert doctor_of_the_repository(tree_root) == [
        (
            "uc-sync.md",
            IMPLEMENTATION_PATH_MISSING,
            "`implementation` names web/app/ui/templates/entry.html, which does not exist in the repository",
        )
    ]


def test_a_hardened_node_is_judged_like_an_implemented_one(tmp_path):
    tree_root = repository_with_a_tree(tmp_path, **{"web/app.py": "x\n"})
    write_node(
        tree_root,
        "uc-sync",
        "use-case",
        parent="fr-offline",
        state="hardened",
        mechanism="a queue",
        implementation="web/gone.py",
        verification=[{"command": "pytest -q", "expects": "it passes"}],
    )
    assert [code for _name, code, _message in doctor_of_the_repository(tree_root)] == [
        IMPLEMENTATION_PATH_MISSING
    ]


def test_paths_that_exist_are_sound_whether_a_file_or_a_folder(tmp_path):
    tree_root = repository_with_a_tree(
        tmp_path, **{"web/app/x.py": "x\n", "web/app/state/y.py": ""}
    )
    built_node(tree_root, "web/app/x.py, web/app/state/ (y.py), web/app/state/y.py::function")
    assert doctor_of_the_repository(tree_root) == []


def test_a_path_before_the_node_is_built_is_not_asked_to_exist(tmp_path):
    tree_root = repository_with_a_tree(tmp_path, **{"web/app.py": "x\n"})
    built_node(tree_root, "web/not_yet.py", state="improvised")
    assert doctor_of_the_repository(tree_root) == []


def test_a_path_relative_to_a_folder_named_earlier_is_not_judged(tmp_path):
    """`web/app/shell/ (answers/puntal_client.py)` is sound prose a root-relative lookup would call
    missing; the check prefers saying nothing to turning a sound tree red."""
    tree_root = repository_with_a_tree(tmp_path, **{"web/app/shell/router.py": "x\n"})
    built_node(tree_root, "web/app/shell/ (answers/puntal_client.py, templates/shell/x.html)")
    assert doctor_of_the_repository(tree_root) == []


def test_a_bare_file_name_and_a_dotted_word_are_not_paths(tmp_path):
    tree_root = repository_with_a_tree(tmp_path, **{"web/app.py": "x\n"})
    built_node(tree_root, "entry.html y http.client, p.ej en web/app.py")
    assert doctor_of_the_repository(tree_root) == []


def test_the_doctor_reads_no_repository_unless_it_is_given_one(tmp_path):
    tree_root = repository_with_a_tree(tmp_path, **{"web/app.py": "x\n"})
    built_node(tree_root, "web/gone.py")
    assert check_tree(load_tree(tree_root)) == []


def test_a_tree_outside_any_repository_has_no_repository_to_check_against(tmp_path):
    outside = tmp_path / "not_a_repository"
    write_sound_tree(outside)
    assert repository_root_of(outside) is None


def test_the_rule_is_in_the_doctors_list_of_checks():
    assert IMPLEMENTATION_PATH_MISSING in CHECKS


def test_validate_fails_a_stale_pointer_and_names_the_node_file(tmp_path, capsys):
    tree_root = repository_with_a_tree(tmp_path, **{"web/app.py": "x\n"})
    built_node(tree_root, "web/gone.py")

    assert cli.main(["validate", "--root", str(tree_root)]) == 1
    assert "uc-sync.md: implementation-path-missing: `implementation` names web/gone.py" in (
        capsys.readouterr().out
    )
