"""The ratchet's rules on in-memory snapshots: no git, no disk."""

from agent_os.quality.ratchet import (
    FILE_TOO_LONG,
    FOLDER_TOO_FULL,
    Limits,
    RepositorySnapshot,
    entries_per_folder,
    find_violations,
)

LIMITS = Limits(max_entries_per_folder=3, max_lines_per_file=10)


def snapshot_of(line_counts_by_path: dict[str, int]) -> RepositorySnapshot:
    return RepositorySnapshot(frozenset(line_counts_by_path), line_counts_by_path.__getitem__)


def violations_between(base, head, excluded_paths=()):
    return find_violations(snapshot_of(base), snapshot_of(head), LIMITS, excluded_paths)


def test_a_new_file_over_the_line_limit_is_a_violation():
    violations = violations_between({"a.py": 1}, {"a.py": 1, "b.py": 11})
    assert [(v.kind, v.path, v.measured, v.measured_on_base) for v in violations] == [
        (FILE_TOO_LONG, "b.py", 11, None)
    ]


def test_a_file_already_over_the_limit_may_shrink_or_stay_but_not_grow():
    assert violations_between({"a.py": 50}, {"a.py": 50}) == []
    assert violations_between({"a.py": 50}, {"a.py": 49}) == []
    grown = violations_between({"a.py": 50}, {"a.py": 51})
    assert [(v.path, v.measured, v.measured_on_base) for v in grown] == [("a.py", 51, 50)]


def test_a_file_at_the_limit_is_compliant():
    assert violations_between({}, {"a.py": 10}) == []


def test_a_new_folder_over_the_entry_limit_is_a_violation():
    head = {f"pkg/{name}.py": 1 for name in "abcd"}
    violations = violations_between({"x.py": 1}, {"x.py": 1, **head})
    assert [(v.kind, v.path, v.measured) for v in violations] == [(FOLDER_TOO_FULL, "pkg", 4)]


def test_a_folder_already_over_the_limit_may_not_gain_an_entry():
    base = {f"pkg/{name}.py": 1 for name in "abcd"}
    assert violations_between(base, base) == []
    assert violations_between(base, {**base, "pkg/e.py": 1}) != []
    assert violations_between(base, {k: v for k, v in base.items() if k != "pkg/a.py"}) == []


def test_a_new_subfolder_counts_as_one_entry_of_its_parent():
    base = {"a.py": 1, "b.py": 1, "c.py": 1}
    violations = violations_between(base, {**base, "sub/d.py": 1})
    assert [(v.path, v.measured) for v in violations] == [("", 4)]


def test_excluded_paths_are_neither_measured_nor_entered_but_occupy_one_entry():
    head = {f"docs/{name}.md": 999 for name in "abcdef"} | {"a.py": 1}
    assert violations_between({}, head, excluded_paths=["docs/"]) == []
    assert entries_per_folder(head, ["docs/"]) == {"": 2}


def test_an_excluded_single_file_is_skipped_by_its_exact_path():
    assert violations_between({}, {"data.yaml": 500}, excluded_paths=["data.yaml"]) == []


def test_exclusion_matches_whole_path_components_not_prefixes_of_a_name():
    assert violations_between({}, {"docsy.py": 500}, excluded_paths=["docs"]) != []


def test_a_violation_describes_itself_with_its_path_and_numbers():
    (violation,) = violations_between({"a.py": 50}, {"a.py": 51})
    assert violation.describe() == (
        "a.py: 51 lines, was 50 on the base (limit 10; an existing one may not get worse)"
    )
