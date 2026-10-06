"""Reads a tree root into records, and into defects for every file that is not one.

The loader's contract is that it never raises over the CONTENT of the tree: a file it cannot read
as a node or a decision becomes a `Defect` with the file's path and a code, and the tree it returns
holds everything that did load. Only the premise of the whole walk -- the root is a directory --
raises, because a doctor run over a path that is not there would pass without having checked a
single file (`tests/test_no_host_literals.py` fails on an empty listing for the same reason).

The root is ONE directory of Markdown files, nodes and decisions together, in whatever
subdirectories the host likes: what a file is comes from its frontmatter `type`, never from where
it sits, and an id is the file's name, so moving a file between folders breaks no pointer.
"""

from __future__ import annotations

import collections.abc
import os
import pathlib
from dataclasses import dataclass, field

import yaml
from pydantic import ValidationError

from agent_os.tree.models import (
    BODY_FIELD_BY_TYPE,
    DECISION_TYPE,
    IDENTIFIER_PATTERN,
    NODE_TYPES,
    RECORD_TYPES,
    Decision,
    Node,
)

MARKDOWN_SUFFIX = ".md"
FRONTMATTER_FENCE = "---"

# The loader's own defect codes. Every other code belongs to `agent_os.tree.checks`.
ORPHAN_FILE = "orphan-file"
BAD_FRONTMATTER = "bad-frontmatter"
SCHEMA = "schema"
DUPLICATE_ID = "duplicate-id"


class _NoDuplicateKeysLoader(yaml.SafeLoader):
    """`yaml.safe_load` keeps the LAST of two equal keys without a word, so a bad merge that leaves
    `premises:` twice would silently drop the first list. In a file a tool trusts field by field,
    that is a defect to report, not a value to pick."""

    def construct_mapping(self, node, deep=False):
        seen: set = set()
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=True)
            if not isinstance(key, collections.abc.Hashable):
                continue  # the parent class refuses an unhashable key with its own message
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"found duplicate key {key!r}", key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep)


class TreeRootError(Exception):
    """The tree root cannot be read at all: it is missing or is not a directory."""


@dataclass(frozen=True)
class Defect:
    """One red line: the file it is about, the named rule it breaks, and what is wrong."""

    path: pathlib.Path
    code: str
    message: str


@dataclass
class Tree:
    """Everything the root held. `nodes` and `decisions` map an id to a record that parsed and is
    the only file claiming that id; the file it came from is in `paths`."""

    root: pathlib.Path
    nodes: dict[str, Node] = field(default_factory=dict)
    decisions: dict[str, Decision] = field(default_factory=dict)
    paths: dict[str, pathlib.Path] = field(default_factory=dict)
    # Ids whose file exists but cannot be used: it did not parse, or two files claim the id. A
    # reference to one of them is not "dangling" -- the target is there and has its own defect --
    # so the reference checks stay quiet about it instead of reporting the same fault twice.
    unusable_ids: set[str] = field(default_factory=set)
    defects: list[Defect] = field(default_factory=list)


def require_tree_root(root: pathlib.Path | str) -> pathlib.Path:
    """`root` as an absolute path, or `TreeRootError`: never a guess at a directory that is not
    there. An EMPTY existing root is a valid, fresh tree; a missing one is almost always a typo."""
    resolved = pathlib.Path(root).resolve()
    if not resolved.is_dir():
        raise TreeRootError(f"tree root {resolved} is not a directory")
    return resolved


def _walk_files(root: pathlib.Path) -> list[pathlib.Path]:
    """Every file under `root`, sorted, skipping what starts with a dot (`.gitkeep`, editor
    droppings): those are not content, and a doctor that failed on `.gitkeep` would only teach
    people to delete it. Everything else, whatever its extension, is a candidate -- the point is
    that a stray file is a red check."""
    found: list[pathlib.Path] = []
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = sorted(name for name in subdirectories if not name.startswith("."))
        found += [
            pathlib.Path(directory) / name for name in sorted(filenames) if not name.startswith(".")
        ]
    return found


def split_frontmatter(text: str) -> tuple[str, str] | None:
    """`(frontmatter text, body)`, or None when the text does not open with a closed `---` block."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != FRONTMATTER_FENCE:
        return None
    for index in range(1, len(lines)):
        if lines[index].rstrip() == FRONTMATTER_FENCE:
            return "".join(lines[1:index]), "".join(lines[index + 1 :])
    return None


def describe_validation_error(error: ValidationError, record_type: str) -> list[str]:
    """One short line per field problem, in the words a person fixing the file needs: pydantic's
    own `Field required` and `Extra inputs are not permitted` say neither which kind of record nor
    what to do."""
    body_field = BODY_FIELD_BY_TYPE[record_type]
    lines = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"])
        kind = item["type"]
        if kind == "missing":
            text = "missing field"
        elif kind == "extra_forbidden":
            text = "unknown field"
        elif kind == "too_short":
            text = "must have at least one entry"
        elif kind == "string_too_short" and location == body_field:
            text = (
                f"the Markdown body is empty (the {body_field} is the text after the frontmatter)"
            )
        elif kind == "string_too_short":
            text = "must not be blank"
        elif kind == "string_pattern_mismatch" and item.get("ctx", {}).get("pattern") == (
            IDENTIFIER_PATTERN
        ):
            text = "must be lowercase words joined by hyphens (a-z, 0-9, -)"
        elif kind == "string_pattern_mismatch":
            text = "must be one line"
        elif kind == "value_error":
            # A rule the model states itself (a verification entry is a command or a judge): its
            # own sentence, without pydantic's "Value error, " prefix.
            text = str(item["ctx"]["error"])
        else:
            text = item["msg"]
        lines.append(f"{location}: {text}" if location else text)
    return lines


@dataclass
class _FileOutcome:
    """What reading one file came to: the record, or the defects that say why there is none and
    the ids a reference might still mean to reach through it (its name, and the `id:` it declared
    when it got far enough to declare one): a reference to either is a reference to a file that is
    there and already reported, not a dangling one."""

    record: Node | Decision | None = None
    defects: list[Defect] = field(default_factory=list)
    claimed_ids: set[str] = field(default_factory=set)


def _read_file(path: pathlib.Path) -> _FileOutcome:
    def rejected(code: str, *messages: str, claimed: set[str]) -> _FileOutcome:
        return _FileOutcome(
            defects=[Defect(path, code, message) for message in messages], claimed_ids=claimed
        )

    if path.suffix != MARKDOWN_SUFFIX:
        return rejected(
            ORPHAN_FILE, "not a Markdown file, so neither a node nor a decision", claimed=set()
        )
    claimed = {path.stem}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        return rejected(ORPHAN_FILE, f"cannot be read as UTF-8 text: {error}", claimed=claimed)
    parts = split_frontmatter(text)
    if parts is None:
        return rejected(
            ORPHAN_FILE,
            "no closed `---` YAML frontmatter block, so neither a node nor a decision",
            claimed=claimed,
        )
    frontmatter_text, body = parts
    try:
        frontmatter = yaml.load(frontmatter_text, Loader=_NoDuplicateKeysLoader)
    except (yaml.YAMLError, ValueError) as error:
        return rejected(
            BAD_FRONTMATTER, f"frontmatter is not valid YAML: {_one_line(error)}", claimed=claimed
        )
    if not isinstance(frontmatter, dict):
        return rejected(BAD_FRONTMATTER, "frontmatter is not a mapping of fields", claimed=claimed)
    if isinstance(frontmatter.get("id"), str):
        claimed.add(frontmatter["id"])
    record_type = frontmatter.get("type")
    if record_type not in RECORD_TYPES:
        shown = "has no `type`" if record_type is None else f"has type {record_type!r}"
        return rejected(
            ORPHAN_FILE,
            f"frontmatter {shown}; neither a node nor a decision "
            f"(a record's type is one of {', '.join(RECORD_TYPES)})",
            claimed=claimed,
        )
    body_field = BODY_FIELD_BY_TYPE[record_type]
    if body_field in frontmatter:
        return rejected(
            SCHEMA,
            f"{body_field}: write it as the Markdown body after the frontmatter, "
            "not as a frontmatter field",
            claimed=claimed,
        )
    model = Decision if record_type == DECISION_TYPE else Node
    try:
        record = model.model_validate({**frontmatter, body_field: body.strip()})
    except ValidationError as error:
        return rejected(SCHEMA, *describe_validation_error(error, record_type), claimed=claimed)
    return _FileOutcome(record=record)


def _one_line(error: Exception) -> str:
    return " ".join(str(error).split())


def load_tree(root: pathlib.Path | str) -> Tree:
    """Reads every file under `root`. See the module docstring for what it never raises."""
    tree = Tree(root=require_tree_root(root))
    files_by_id: dict[str, list[pathlib.Path]] = {}
    records: dict[pathlib.Path, Node | Decision] = {}
    for path in _walk_files(tree.root):
        outcome = _read_file(path)
        tree.defects += outcome.defects
        if outcome.record is None:
            tree.unusable_ids |= outcome.claimed_ids
            continue
        records[path] = outcome.record
        files_by_id.setdefault(outcome.record.id, []).append(path)
    for record_id, claimants in files_by_id.items():
        if len(claimants) > 1:
            tree.unusable_ids.add(record_id)
            for path in claimants:
                others = ", ".join(str(other) for other in claimants if other != path)
                tree.defects.append(
                    Defect(path, DUPLICATE_ID, f"id {record_id!r} is also claimed by {others}")
                )
            continue
        (path,) = claimants
        record = records[path]
        tree.paths[record_id] = path
        if record.type in NODE_TYPES:
            tree.nodes[record_id] = record
        else:
            tree.decisions[record_id] = record
    return tree
