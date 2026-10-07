"""The `tree:` and `board:` sections of a host's `config/agents.yaml`: where the product tree lives,
how its tickets are named, and the GitHub Project its progress board is generated into.

Imports nothing from `agent_os.lib` because `lib` imports it to declare the sections, and a cycle
there would make them unloadable (the same arrangement as `agent_os.quality.config`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TreeConfig(Strict):
    """Where a host's product tree lives and how the tickets compiled from it are named
    (`agent_os.product.tree`, Phase 1 of `docs/AGENTOS_V2_PLAN.md`)."""

    # The directory holding the product tree AND the decision ledger -- one directory of Markdown
    # files, nodes and decisions together, in any subdirectories the host likes -- relative to the
    # host's root. `agent-os-tree --root` overrides it for one run.
    root: str = "product"
    # The worker class a compiled ticket names in its `<!-- budget: <class> -->` line. Empty by
    # default, like `project.guard_unit`: a mechanism that does not know a host's class names does
    # not invent one, so `agent-os-tree compile` refuses until this or `--budget-class` says which.
    ticket_budget_class: str = ""
    # Labels every compiled ticket carries besides its task type label -- a host marks the tickets
    # that came from its tree, or names the module they belong to, here. The initial `status:*`
    # label is deliberately not decided by `compile`: creating the issues is Phase 2's wiring.
    ticket_labels: list[str] = []
    # True makes this a v2 host: dispatch starts only tickets with a node address, dependencies
    # first, never two on the same code (`agent_os.product.dispatch.rules`).
    dispatch_by_node: bool = False


class BoardConfig(Strict):
    """The GitHub Project the progress board of the product tree is generated into
    (`agent_os.product.board`, `agent-os-tree board`). The Project is a view; the tree's files stay
    the record."""

    # The `--owner` of every `gh project` call: a user or an organization login. `@me` is the
    # authenticated user, so the default needs no host literal.
    owner: str = "@me"
    # The Project's number. 0 (the default) finds it by `title` among the owner's Projects and, on a
    # real sync, creates it when none has that title.
    number: int = 0
    title: str = "Agentos progress board"
    # A text field on each item holding the one-line count of its parts by state.
    progress_field: str = "Progress"
    # A number field the owner fills by hand: a lower number comes first. Sync creates it and never
    # writes it; `agent-os-tree board order` reads it back.
    order_field: str = "Order"
