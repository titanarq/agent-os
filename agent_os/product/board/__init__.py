"""The progress board: a GitHub Project generated from the product tree, as a view.

The tree's files stay the memory of record
(`docs/tree/dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check.md`); the Project is rebuilt
from them and never read back except for what only the owner can write there: the order of the
backlog. Everything reaches GitHub through `gh project`, and a test puts a fake `gh` first in PATH.

- `agent_os.product.board.branches` -- a branch (a requirement and its parts) and how it renders.
- `agent_os.product.board.project` -- `GhProjectClient`, the only module that runs `gh`.
- `agent_os.product.board.sync` -- the idempotent plan and its application.
- `agent_os.product.board.order` -- the owner's order of the backlog, read back.
- `agent_os.product.board.cli` -- `agent-os-tree board sync|order`.
"""
