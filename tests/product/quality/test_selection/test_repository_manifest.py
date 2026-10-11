from agent_os.cli import AGENT_OS_DIR
from agent_os.product.test_selection.checks import check_manifest
from agent_os.product.test_selection.manifest import load_manifest


def test_the_repositorys_own_manifest_maps_every_test_file_to_a_group():
    manifest = load_manifest(AGENT_OS_DIR, "tests/selection")
    assert check_manifest(manifest, AGENT_OS_DIR) == []
