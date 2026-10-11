import pytest
from selection_support import SINGLE_MANIFEST, write_file

from agent_os.product.test_selection.manifest import (
    DEFAULT_TEST_GLOBS,
    ManifestError,
    ManifestNotFoundError,
    load_manifest,
)


def test_a_single_file_loads_with_its_defaults(tmp_path):
    write_file(
        tmp_path, "m.yaml", "groups:\n  - id: a\n    covers: [x/]\n    tests: [tests/t.py]\n"
    )
    manifest = load_manifest(tmp_path, "m.yaml")
    assert manifest.groups[0].id == "a"
    assert manifest.settings.test_globs == DEFAULT_TEST_GLOBS
    assert manifest.settings.always == ()


def test_an_unknown_key_is_a_loud_error(tmp_path):
    write_file(tmp_path, "m.yaml", "groups:\n  - id: a\n    cover: [x/]\n")
    with pytest.raises(ManifestError, match="cover"):
        load_manifest(tmp_path, "m.yaml")
    write_file(tmp_path, "m.yaml", "gruops: []\n")
    with pytest.raises(ManifestError, match="gruops"):
        load_manifest(tmp_path, "m.yaml")


def test_a_folder_is_read_recursively_with_settings_only_in_settings_yaml(tmp_path):
    write_file(tmp_path, "m/settings.yaml", "always: [tests/g.py]\nexempt: [docs/]\n")
    write_file(tmp_path, "m/area/one.yaml", "groups:\n  - id: a\n    tests: [tests/a.py]\n")
    write_file(tmp_path, "m/two.yaml", "groups:\n  - id: b\n    tests: [tests/b.py]\n")
    manifest = load_manifest(tmp_path, "m")
    assert [group.id for group in manifest.groups] == ["a", "b"]
    assert manifest.settings.always == ("tests/g.py",)


def test_settings_in_another_file_of_a_folder_are_refused(tmp_path):
    write_file(tmp_path, "m/two.yaml", "always: [tests/x.py]\n")
    with pytest.raises(ManifestError, match="only `settings.yaml`"):
        load_manifest(tmp_path, "m")


def test_a_missing_manifest_is_not_an_invalid_one(tmp_path):
    with pytest.raises(ManifestNotFoundError):
        load_manifest(tmp_path, "nope.yaml")


def test_the_shared_example_manifest_parses(tmp_path):
    write_file(tmp_path, "m.yaml", SINGLE_MANIFEST)
    assert len(load_manifest(tmp_path, "m.yaml").integration) == 1
