# The doctor resolves the root-relative paths of a built node's `implementation`

- Date: 2026-10-09
- Status: accepted
- Modules: `agent_os/product/tree/implementation_paths.py`, `agent_os/product/tree/checks.py`
- Plan: `docs/tree/dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check.md`, `docs/tree/dec-tree-as-repo-files.md`

## Context
The doctor's scope (ADR 2026-10-04) left out checking that an implementation pointer resolves: it reads one
snapshot of the tree. In the first v2 host two nodes kept naming `web/app/ui/templates/entry.html` after another
ticket deleted it, and nothing was red. `implementation` is prose in the owner's language, full of paths relative
to a folder named earlier in the sentence, bare file names and dotted words.

## Decision
`check_tree` takes an optional `repository_root` and, given one, reports `implementation-path-missing` for an
`implemented` or `hardened` node whose `implementation` names a path that does not exist. It is built for
precision: only words with a `/` whose first folder exists at the repository root are judged. `agent-os-tree
validate` finds the repository from the tree root's git checkout; `compile` and `slice` do not pass it, so one
stale pointer never stops every other ticket.

## Consequences
- A false positive turns a sound tree red, so the rule says nothing about what it cannot resolve; on the host's
  five checkouts it named only the two nodes above.
- A node that deliberately remembers a deleted file in its prose ("que se quitan") is reported too: the pointer is
  stale and the sentence is rewritten.
- A tree outside any git checkout is not checked.
