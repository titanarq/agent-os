"""Which changed paths are node files of the product tree, and the ancestors of each node."""

from __future__ import annotations

import pathlib
from collections.abc import Collection

from agent_os.product.test_selection.paths import entry_holds_path
from agent_os.product.tree.loader import MARKDOWN_SUFFIX, load_tree


def node_ids_by_changed_path(changed_paths: Collection[str], tree_root: str) -> dict[str, str]:
    """A changed `.md` file under the tree root names its node by its stem (the tree's rule)."""
    if not tree_root:
        return {}
    return {
        path: pathlib.PurePosixPath(path).stem
        for path in changed_paths
        if path.endswith(MARKDOWN_SUFFIX) and entry_holds_path(tree_root, path)
    }


def ancestors_by_node_id(repository: pathlib.Path, tree_root: str) -> dict[str, list[str]]:
    """Each usable node's ancestors by `parent`, nearest first; empty when there is no tree."""
    if not tree_root or not (repository / tree_root).is_dir():
        return {}
    nodes = load_tree(repository / tree_root).nodes
    ancestors: dict[str, list[str]] = {}
    for node_id in nodes:
        chain: list[str] = []
        parent = nodes[node_id].parent
        while parent is not None and parent not in chain and parent != node_id:
            chain.append(parent)
            parent = nodes[parent].parent if parent in nodes else None
        ancestors[node_id] = chain
    return ancestors
