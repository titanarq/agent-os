# The product tree and the decision ledger are Markdown files with a doctor, and `compile` only renders

- Date: 2026-10-04
- Status: accepted
- Modules: tree (`agent_os/tree/`), config, docs
- Implements Phase 1 of `docs/AGENTOS_V2_PLAN.md`; the founding decision "Tree as repo files, issues
  as generated dispatch tickets" is `docs/ledger/dec-tree-as-repo-files.md`

## Context
Agentos v2 adds a product layer to the substrate: a tree of global goals, functional requirements
and use cases, and a ledger of decisions with premises, review triggers and friction. The plan
decides WHAT (files in the host's repository; a doctor that is a red check; a slice per node;
tickets generated from dispatchable nodes). It leaves open the format, which is what everything
later reads: Phase 2 wires tickets to workers, Phase 3 loads a real product into it, and "the
schemas survive Phase 3's real content load without daily rework" is the exit criterion.

Two forces shape it. Context per call is what is contained, so the unit an agent gets must be
small and must not grow with the tree. And order is a red check, not an exhortation: a rule that
lives only in a prompt gets forgotten, so every rule a tree must satisfy has to be a check that
fails the way a host literal fails `tests/test_no_host_literals.py`.

## Decision
- **One root, one kind of file.** The tree and the ledger live in one directory (`tree.root`,
  `--root`), one Markdown file with YAML frontmatter per record, nodes and decisions together, in
  whatever subdirectories a host likes. A record's kind is its frontmatter `type` (`goal`,
  `functional-requirement`, `use-case`, `decision`), never its location, so a root can hold only
  decisions -- which is what this repository's own ledger is -- and a host can move a file without
  touching a pointer. A file under the root that is not a record is `orphan-file`, red; names that
  start with a dot are not content. A prose field (a node's description, a decision's statement) is
  the Markdown body, so a file reads, and diffs, as a document.
- **An id is a stable address, not a position.** `<prefix>-<slug>`: `goal-`, `fr-`, `uc-`, `dec-`
  and lowercase words joined by hyphens, equal to the filename without `.md`. The prefix makes a
  listing, a grep and a ticket marker legible and a type edited without its id a red check. No
  position is encoded: re-parenting a node edits one `parent:` line and breaks nothing. Hierarchical
  addresses (`G1/FR2/UC3`) would break on every re-parent; numeric sequences collide when two
  parallel workers each add "the next" record.
- **Schema is shape, rules are named codes.** The pydantic models (`Strict`, an unknown field is an
  error) say which fields exist, which are required and of what type. Everything else -- an id that
  matches its file, a parent of the right type, a hardened node with an implementation pointer, a
  node pointing at a superseded decision -- is a rule in `agent_os/tree/checks.py` with its own code,
  so each red line has a name to grep for and a row in `docs/AGENT_OS.md`, and a test keeps the code
  list and the docs equal.
- **The state machines are checked as snapshots.** The doctor checks what one snapshot can hold:
  a `hardened` node has an implementation pointer and a verification; a `superseded` decision names
  an existing successor and the chain does not loop; no node points at a superseded decision (the
  line names the live successor); an `under-review` decision is legal wherever an `in-force` one is,
  because it is still obeyed. It does NOT check that a state *transition* was legal (`hardened`
  back to `pending`): that needs two snapshots, so a git base, and is left for when a transition
  actually goes wrong. It does not run a verification or resolve an implementation pointer either.
  `pending` to `hardened` directly is legal -- a foundation node is built as a normal issue and
  never improvised (`foundation-improvised`) -- so the machine is not the strictly linear one the
  plan's arrow suggests.
- **A goal is not a work item.** It carries no mechanism, implementation, spike, foundation flag or
  non-pending state (`goal-carries-work-fields`). It may carry a `verification`, which is acceptance
  and never dispatched work: a goal is still never a ticket. A functional requirement and a use case
  must declare `mechanism`, as text or `pending`, so deferring it is a visible choice and not an
  omission.
- **The slice is the chain, nothing else.** `context NODE` emits the node in full, its ancestors up
  to the goal, and the decisions in force on that chain (the node's own and every ancestor's, since
  a decision on a requirement binds its use cases), with their sources. Each decision brings its
  statement, premises, rejected alternatives and review triggers -- what a worker needs to obey it
  and to know not to relitigate it -- and only the COUNT of its friction entries, which grow without
  bound. Each ancestor also brings the verification it carries (commands and `expects`), labelled as
  the acceptance the node's work serves and must not break: the evaluators above the work are in the
  chain, so they cost one chain and no more. An `under-review` decision is included and labelled as
  still obeyed; a superseded one never is. No sibling, descendant or unrelated decision appears, so
  the size depends on the length of one chain and not on the tree (a test compares the very same
  bytes against a tree with over nine hundred more nodes). The output is deterministic: ordered by
  chain, then by id.
- **The slice asks the doctor.** It is refused, printing the doctor's lines, when any file it is made
  of fails a check; a defect in another branch does not stop it. One implementation of "is this file
  sound", not a second copy of the rules in the slicer.
- **Which nodes become tickets.** A functional requirement or use case that is `pending`, has an
  executable `verification`, and whose mechanism is resolvable: written, or `pending` with no spike
  that found it `infeasible`. A pending node that lacks a verification, or whose pending mechanism a
  spike found infeasible, is an ESCALATION entry with a code and a reason, never a ticket. A node
  with children is a *container* -- its use cases are the work -- and is skipped without comment,
  whether or not it has a verification of its own; demanding a verification of every requirement
  would escalate every decomposed requirement of a real tree, and a requirement's verification, when
  it has one, is the acceptance of its subtree and not a ticket. Goals and nodes past `pending` are
  not dispatched by this step. Foundation nodes are listed first.
- **A ticket is a dispatchable issue.** Its body has the seven sections of
  `agent_os.lib.REQUIRED_SECTIONS` in order, the `<!-- budget: <class> -->` line and a second marker,
  `<!-- node: <id> -->`, the address Phase 2 finds a ticket's node and a node's ticket by. Every body
  is checked with `validate_issue_body` before it is returned, so a ticket the dispatcher would
  refuse is never rendered. The budget class is `--budget-class` or `tree.ticket_budget_class`,
  empty by default and a worker class when set (checked when the config loads): the mechanism does
  not know a host's class names and does not guess one.
- **`compile` only renders.** It returns text, JSON and files and calls no `gh`, no network and no
  backend; it refuses a tree the doctor finds anything in. A ticket is a durable record in an
  external tracker and outlives the tree that produced it, so rendering from a broken tree is the
  expensive mistake, and creating one is a step with decisions of its own (which identity, which
  initial `status:*` label, how a re-run finds the ticket a node already has, the parent link) that
  belong to Phase 2's wiring. Keeping them apart also lets the render be run by anyone as a dry run
  of what a tree would dispatch, and be tested with no tracker.
- **The founding decisions forced four things into the decision format.** Mapping the plan's table
  onto the schema: a trigger cell is often "A, or B", so `review_triggers` is a list, each entry
  checkable on its own; one trigger is measured in time ("unused after 2 months"), so a decision has
  `decided`; the table has no column of rejected alternatives and some can only be inferred, so each
  carries `basis: stated | implied`, which keeps an invented alternative from passing as history --
  the risk when an LLM fills a ledger; and a decision needs `sources`, because "approved in a design
  discussion" is provenance a consolidator will want. A decision about the mechanism itself, with no
  node pointing at it, is a legal ledger entry.
- **Friction lives in the decision file.** A `friction` list of dated entries, each optionally naming
  a node and a pointer to the evidence. It is the simplest thing that holds "entries against the
  decision's id" and lets the consolidator read a decision and its friction in one file.

**Changed 2026-10-06, before merge, by the owner's decision that tests run top-down from the
goals.** A goal's tests are the evaluators that keep the work under it from drifting; the tests
written bottom-up at the leaves consolidate reliability. Two rules of the first draft contradicted
that, and a third piece was missing. (1) A goal used to be forbidden a `verification`
(`goal-carries-work-fields`); it may now carry one -- acceptance, not work, so a goal is still never
a ticket -- and still no mechanism, implementation, spike, foundation flag or state other than
`pending`. (2) `compile` used to treat a node with children as a container only when it had no
verification, so a requirement with use cases and a verification of its own would have been
dispatched as a ticket on top of its own use cases; a node with children is now a container
whatever it carries, and its verification is the acceptance of its subtree. (3) The slice now
shows the verification of every ancestor, labelled as acceptance to serve and not break, so the
agent working on a use case is told which evaluators stand above it (and so does a ticket, whose
Context is the slice). Nothing else in the format moved.

## Consequences
- A host gets a tree and a ledger it can diff, review and gate in CI, and every red line has a code.
  A host wires the gate itself: `agent-os-tree validate` in its test command, or `check_tree` from
  a test. `agent-os-install` does not write it yet.
- One broken file makes `compile` refuse the whole tree, so one bad node blocks every ticket. The
  tree is meant to be green on its main branch because CI enforces it; the alternative, compiling
  the sound branches of a broken tree, was rejected because a half-trusted tree is how a wrong
  ticket gets out.
- The doctor trusts a verification command to be real. It cannot tell `true` from a test, and no
  transition check stops a hardened node being edited back. Both are left for evidence that they
  matter.
- There is no node-to-node dependency field: every ticket says `Dependencies: none`. The plan does
  not ask for one, and a `Blocked by #N` line needs issue numbers that exist only after Phase 2
  creates the issues. A real tree where use cases wait on a foundation node will need it.
- Friction appended by two parallel pull requests to the same decision conflicts textually at the
  end of the list. **What would revert this**: such conflicts in practice. The move is friction as
  one file per entry, referencing the decision's id; the entry shape stays the same.
- A spike's shape is minimal (`question`, `outcome`, `finding`, `date`); the expert role of Phase 3
  will show what it needs to record, and the field is closed by `Strict` until then.
- A superseded decision keeps its file and its friction as history, and never reaches a slice.
