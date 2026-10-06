"""The product tree and the decision ledger of Agentos v2 (Phase 1 of `docs/AGENTOS_V2_PLAN.md`).

A host's product is described as files in its own repository: a tree of nodes (global goals,
functional requirements, use cases) and a ledger of decisions, one Markdown file with YAML
frontmatter per record. This package defines what a record is, checks a directory of them the way
`tests/test_no_host_literals.py` checks for host literals (a violation is a red check, not an
exhortation), cuts the slice of it one agent needs, and renders dispatch tickets from the nodes
that are ready to be worked. It touches no network and no backend.

The binding decisions about its shape are
`docs/adr/2026-10-04-the-product-tree-and-the-decision-ledger-are-markdown-files-with-a-doctor.md`.

The modules:

- `agent_os.product.tree.models` -- the pydantic schemas of a node and of a decision.
- `agent_os.product.tree.loader` -- reads a tree root into records, and into defects for what is not one.
- `agent_os.product.tree.checks` -- the doctor: every rule a tree must satisfy, one named code each.
- `agent_os.product.tree.reference_checks` -- the doctor's checks on decision pointers, supersession and `depends_on`.
- `agent_os.product.tree.hardening` -- what keeps a node from hardening (open `what` question, challenge).
- `agent_os.product.tree.slicing` / `slicing_fields` -- the slice of one node: its chain of ancestors and the decisions on it.
- `agent_os.product.tree.compile` -- dispatch tickets from dispatchable nodes, escalations from the rest.
- `agent_os.product.tree.trailers` -- the `Node-Change` trailer every commit touching the tree carries.
- `agent_os.product.tree.cli` -- `agent-os-tree validate|doctor|context|compile|trailers`.
"""
