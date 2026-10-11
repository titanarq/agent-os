"""The `tree:`, `board:`, `puntal:` and `interpreter:` sections of a host's `config/agents.yaml`: where
the product tree lives, how its tickets are named, the GitHub Project its progress board is generated
into, how a puntal reaches the app and how the feedback interpreter talks.

Imports nothing from `agent_os.lib` because `lib` imports it to declare the sections, and a cycle
there would make them unloadable (the same arrangement as `agent_os.quality.config`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


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
    # Files besides goal nodes that are the owner's what -- the evaluators of the method: the
    # composition of its battery, the thresholds of its indicators, the rule that tells what from
    # how -- as `fnmatch` globs on repository paths. A pull request touching one, or a goal node, is
    # never merged automatically (`agent-os-sessions guard-what`). Empty by default: a mechanism
    # does not know where a host keeps its evaluators.
    owner_only_paths: list[str] = []
    # The directory the product writes a test session's file into when the owner closes the
    # session (`<id>.json`, the contract of `docs/AGENT_OS.md` §4.11), relative to the host's root
    # unless absolute. `agent-os-sessions test-ingest` reads it. The default is a name, not a
    # location the host's data already has: a host sets this key to where its product writes.
    test_sessions_dir: str = "var/test-sessions"


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


class PuntalConfig(Strict):
    """How a puntal (Agentos v2) reaches the app it stands in for and how long it may take
    (agent_os/docs/adr/2026-10-04-a-puntal-is-a-one-shot-headless-process-under-its-own-class-and-
    cannot-write-code.md). Every key is optional, but the driver refuses to run without a
    persistence command and, on its default path, without an executor command."""

    # The app's persistence API: the command (shell-split) behind `./state get tickets T-1` and the
    # pre-helper's reads. `--persistence-command` and `PUNTAL_PERSISTENCE_COMMAND` outrank it.
    persistence_command: str = ""
    # A text file (relative to the host's root) describing its subcommands, rendered at
    # `__PERSISTENCE_API__` in both paths' contracts (the fast one, with no tool, reads it).
    persistence_api_file: str = ""
    # The app's EXECUTOR: the command (shell-split) that applies a plan's operations atomically
    # (agent_os/product/puntal/fast/executor.py). Empty makes the fast path refuse unless the caller
    # asks for the plan alone. `--executor-command` and `PUNTAL_EXECUTOR_COMMAND` outrank it.
    executor_command: str = ""
    # The words a node's declared read may start with: subcommands that change nothing.
    read_subcommands: list[str] = ["get", "list"]
    executor_timeout_seconds: int = 30  # the executor is on the click's critical path: cut after
    # A model turn's process group is killed after this many seconds: a SAFETY for a person waiting
    # on a click, not a budget (spend is bounded by the class's ceilings).
    timeout_seconds: int = 90
    # The slow path's loop guard: most tool calls before the driver cuts it.
    max_tool_calls: int = 12
    # `claude --effort`. Empty leaves the CLI's own default.
    effort: str = ""
    # The model of the actions that the class's own model (`classes.puntal.model`) answers badly:
    # `{action: model}`, where the key is the `action` of the request. An action not named here runs
    # on the class's model; `--model` outranks both. The telemetry records the effective model.
    action_models: dict[str, str] = {}

    @field_validator("action_models")
    @classmethod
    def every_model_named(cls, value: dict[str, str]) -> dict[str, str]:
        empty = sorted(action for action, model in value.items() if not model.strip())
        if empty:
            raise ValueError(f"names no model for {empty}: remove the action to use the class's")
        return value

    @field_validator("timeout_seconds", "max_tool_calls", "executor_timeout_seconds")
    @classmethod
    def positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be at least 1")
        return value


class InterpreterConfig(Strict):
    """How the feedback interpreter (`agent_os.product.interpreter`) talks and how long it may take.
    The model and the per-invocation ceilings are the `interpreter` class's, as the puntal's are its
    class's. Every key is optional."""

    # The language of the interpreter's `reply`. Empty (the default) means the language the owner's
    # latest message is written in, so a host needs no key unless it wants one fixed language; a
    # name such as `Spanish` fixes it whatever the owner writes. Items' `summary` stay in the
    # language of the thread: the ingestion turns them into tickets in the host's own language.
    reply_language: str = ""
    # Kills the model's process group after this many seconds: a SAFETY for an owner waiting in a
    # chat, not a budget (spend is bounded by the class's ceilings).
    timeout_seconds: int = 60
    # `claude --effort`. Empty leaves the CLI's own default.
    effort: str = ""
    # The most recent messages of the thread the brief carries (the owner's new message and the
    # already-interpreted items are always carried whole). A long session stays cheap per message.
    max_thread_messages: int = 40

    @field_validator("timeout_seconds", "max_thread_messages")
    @classmethod
    def positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be at least 1")
        return value
