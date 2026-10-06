---
id: dec-tree-as-repo-files
type: decision
title: Tree as repo files, issues as generated dispatch tickets
state: in-force
decided: 2026-10-04
sources:
  - "docs/AGENTOS_V2_PLAN.md, 'Founding decisions' row 2 and 'The three layers'; approved by the owner in the design discussion of 2026-10-04"
premises:
  - "Structured deep trees are unreadable and expensive in GitHub Issues"
  - "Slice reads must be cheap and diffable"
rejected_alternatives:
  - option: "GitHub Issues as the tree store: the tree itself as a hierarchy of issues"
    reason: "The premises argue it: a structured deep tree is unreadable and expensive there, and a slice read has to be cheap and diffable"
    basis: stated
  - option: "A store other than files in git, such as a database or a service"
    reason: "Implied by the review triggers, which name the conditions under which a non-git store would be revisited (slicing as the bottleneck, concurrent non-git writers); not argued at approval, so no reason for rejecting it is on record"
    basis: implied
review_triggers:
  - "Tree slicing becomes the bottleneck"
  - "A host needs concurrent non-git writers"
---
The product tree (global goals, functional requirements, use cases) is stored as files in the
host's own repository, one Markdown file per node. GitHub Issues are not the tree: they are
generated from it, as dispatch tickets, by `agent-os-tree compile`, and each carries the address of
the node it came from.
