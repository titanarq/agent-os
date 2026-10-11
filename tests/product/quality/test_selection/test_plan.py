from agent_os.product.test_selection.manifest import Group, Integration, Manifest, Settings
from agent_os.product.test_selection.manifest_changes import ManifestChange
from agent_os.product.test_selection.plan import plan_tests

MANIFEST = Manifest(
    settings=Settings(always=("tests/test_guard.py",), exempt=("docs/changelog/",)),
    groups=(
        Group(
            id="worker", covers=("bin/worker.sh", "lib/worker/"), tests=("tests/test_worker.py",)
        ),
        Group(
            id="prompts",
            nodes=("uc-prompts",),
            covers=("prompts/",),
            tests=("tests/test_prompts.py",),
        ),
        Group(id="idle", covers=("idle/",), tests=("tests/test_idle.py",)),
    ),
    integration=(
        Integration(id="both", sides=("worker", "prompts"), tests=("tests/test_both.py",)),
    ),
)


def plan(paths, nodes=None, ancestors=None, change=None):
    return plan_tests(MANIFEST, paths, nodes or {}, ancestors or {}, change)


def test_a_covered_path_selects_its_group_and_always_runs():
    result = plan(["bin/worker.sh"])
    assert result.mode == "selected"
    assert result.groups == ("worker",)
    assert "tests/test_worker.py" in result.tests and "tests/test_guard.py" in result.tests


def test_a_directory_covers_what_is_under_it():
    assert plan(["lib/worker/deep/x.py"]).groups == ("worker",)


def test_a_changed_test_file_selects_its_group():
    assert plan(["tests/test_idle.py"]).groups == ("idle",)


def test_a_node_file_selects_groups_listing_the_node_or_an_ancestor():
    ancestors = {"uc-child": ["fr-parent", "uc-prompts"]}
    result = plan(["product/uc-child.md"], {"product/uc-child.md": "uc-child"}, ancestors)
    assert result.mode == "selected" and result.groups == ("prompts",)


def test_a_node_nobody_lists_is_unmapped_and_runs_full():
    result = plan(["product/uc-x.md"], {"product/uc-x.md": "uc-x"})
    assert result.mode == "full" and result.unmapped_paths == ("product/uc-x.md",)


def test_an_integration_with_a_selected_side_contributes_its_tests():
    assert "tests/test_both.py" in plan(["prompts/p.md"]).tests
    assert "tests/test_both.py" not in plan(["idle/x.py"]).tests


def test_an_unmapped_path_is_the_fail_safe_full_naming_up_to_ten():
    paths = [f"unknown/{number:02d}.py" for number in range(12)]
    result = plan(paths)
    assert result.mode == "full"
    assert "unknown/09.py" in result.reason and "unknown/10.py" not in result.reason
    assert len(result.unmapped_paths) == 12


def test_an_exempt_path_affects_no_test():
    result = plan(["docs/changelog/n.md"])
    assert (
        result.mode == "selected"
        and result.groups == ()
        and result.tests == ("tests/test_guard.py",)
    )


def test_a_manifest_change_selects_the_groups_added_or_changed():
    change = ManifestChange(frozenset({"m.yaml"}), frozenset({"idle"}), False)
    result = plan(["m.yaml"], change=change)
    assert result.mode == "selected" and result.groups == ("idle",)


def test_a_change_to_exempt_or_always_is_full():
    change = ManifestChange(frozenset({"m.yaml"}), frozenset(), True)
    assert plan(["m.yaml"], change=change).mode == "full"
