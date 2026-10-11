import pytest
from selection_support import (
    commit_all,
    git,
    make_repository,
    write_file,
)

from agent_os.product.test_selection.changed_paths import changed_paths
from agent_os.quality.git_snapshots import GitError


def test_modified_added_and_deleted_paths(repository):
    write_file(repository, "other.txt", "changed\n")
    write_file(repository, "added.txt")
    (repository / "bin/worker.sh").unlink()
    commit_all(repository)
    assert changed_paths(repository, "main") == ["added.txt", "bin/worker.sh", "other.txt"]


@pytest.fixture
def repository(tmp_path):
    return make_repository(tmp_path)


def test_a_rename_is_both_paths(repository):
    git(repository, "mv", "other.txt", "renamed.txt")
    commit_all(repository)
    assert changed_paths(repository, "main") == ["other.txt", "renamed.txt"]


def test_the_merge_base_is_used_when_the_base_moved_on(repository):
    write_file(repository, "mine.txt")
    commit_all(repository)
    git(repository, "checkout", "-q", "main")
    write_file(repository, "theirs.txt")
    commit_all(repository)
    git(repository, "checkout", "-q", "feature")
    assert changed_paths(repository, "main") == ["mine.txt"]


def test_an_unresolvable_base_or_a_missing_git_raises(repository, tmp_path):
    with pytest.raises(GitError):
        changed_paths(repository, "no-such-ref")
    with pytest.raises(GitError):
        changed_paths(tmp_path / "not-a-repository", "main")
