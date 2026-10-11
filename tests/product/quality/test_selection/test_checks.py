import pytest
from selection_support import make_repository, write_file

from agent_os.product.test_selection.checks import check_manifest
from agent_os.product.test_selection.manifest import load_manifest


def defects_of(repository):
    return check_manifest(load_manifest(repository, "manifest.yaml"), repository)


@pytest.fixture
def repository(tmp_path):
    return make_repository(tmp_path)


def test_a_consistent_manifest_has_no_defects(repository):
    assert defects_of(repository) == []


def test_a_test_file_no_group_maps_is_named_with_what_to_do(repository):
    write_file(repository, "tests/sub/test_new.py")
    (defect,) = defects_of(repository)
    assert "`tests/sub/test_new.py` is mapped by no group: add it to the group" in defect
    assert "`manifest.yaml`" in defect


def test_a_mapped_path_that_does_not_exist(repository):
    (repository / "tests/test_worker.py").unlink()
    (defect,) = defects_of(repository)
    assert "`tests/test_worker.py` does not exist" in defect


def test_an_integration_side_that_is_no_group_and_fewer_than_two_sides(repository):
    write_file(
        repository,
        "manifest.yaml",
        "groups:\n  - id: a\n    tests: [tests/test_worker.py]\n"
        "integration:\n  - id: i\n    sides: [a, ghost]\n"
        "  - id: j\n    sides: [a]\n",
    )
    text = "\n".join(defects_of(repository))
    assert "side `ghost`, which is not a group id" in text
    assert "`j` has fewer than two sides" in text


def test_a_duplicated_group_or_integration_id(repository):
    write_file(
        repository,
        "manifest.yaml",
        "groups:\n  - id: a\n    tests: [tests/test_worker.py]\n  - id: a\n"
        "integration:\n  - id: i\n    sides: [a, a]\n  - id: i\n    sides: [a, a]\n",
    )
    text = "\n".join(defects_of(repository))
    assert "group id `a` is declared 2 times" in text
    assert "integration id `i` is declared 2 times" in text
