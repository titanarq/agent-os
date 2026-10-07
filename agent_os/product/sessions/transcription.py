"""Does a pull request transcribe a session answer exactly, and nothing else?

The validator runs this on a pull request that claims to carry the owner's answer
(`docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`). The pull request is
the owner's word only if every file it changes is a node whose sole difference from the base is an
open question of `what` that now reads `answered` with the owner's reply as its `finding`, word for
word -- or a reclaimed decision added as a new open question. Any other change, in any file, is
not a transcription, and the answer cannot stand in for the owner's merge.
"""

from __future__ import annotations

from agent_os.product.sessions.reply import ResolvedReply
from agent_os.product.sessions.what_guard import (
    BASE,
    HEAD,
    FileChange,
    FileReader,
    is_under,
    read_frontmatter,
)


def _is_the_answer(base_entry: dict, head_entry: dict, node_id: str, reply: ResolvedReply) -> bool:
    if not (
        base_entry.get("kind") == "question"
        and base_entry.get("scope") == "what"
        and base_entry.get("outcome") == "open"
        and head_entry.get("outcome") == "answered"
    ):
        return False
    unchanged = {
        key: base_entry.get(key) for key in base_entry if key not in ("outcome", "finding")
    }
    head_rest = {
        key: head_entry.get(key) for key in head_entry if key not in ("outcome", "finding")
    }
    return unchanged == head_rest and any(
        answer.node_id == node_id
        and answer.question == base_entry.get("question")
        and answer.answer == head_entry.get("finding")
        for answer in reply.answers
    )


def _is_a_reclaimed_question(entry: dict, node_id: str, reply: ResolvedReply) -> bool:
    return (
        entry.get("kind") == "question"
        and entry.get("scope") == "what"
        and entry.get("outcome") == "open"
        and any(
            digest["node"] == node_id and digest["decision"] == entry.get("default_answer")
            for digest in reply.reclaimed_digest_entries
        )
    )


def _problems_in_one_node(path: str, base: dict, head: dict, reply: ResolvedReply) -> list[str]:
    node_id = head.get("id")
    base_rest = {key: value for key, value in base.items() if key != "experiments"}
    head_rest = {key: value for key, value in head.items() if key != "experiments"}
    if base_rest != head_rest:
        return [f"{path}: changes more than its experiments"]
    base_entries, head_entries = base.get("experiments") or [], head.get("experiments") or []
    if len(head_entries) < len(base_entries):
        return [f"{path}: removes an experiment"]
    problems = [
        f"{path}: experiment {index + 1} is changed but is not an answer"
        for index, base_entry in enumerate(base_entries)
        if head_entries[index] != base_entry
        and not _is_the_answer(base_entry, head_entries[index], node_id, reply)
    ]
    extra = head_entries[len(base_entries) :]
    problems += [
        f"{path}: adds an experiment that is not a reclaimed question"
        for entry in extra
        if not _is_a_reclaimed_question(entry, node_id, reply)
    ]
    return problems


def verify_transcription(
    changes: list[FileChange], *, tree_root: str, read_file: FileReader, reply: ResolvedReply
) -> list[str]:
    """One line per way the pull request is more than a transcription; empty when it is exactly one."""
    if not changes:
        return ["the pull request changes no file"]
    problems = []
    for change in changes:
        if change.previous_path or not is_under(change.path, tree_root):
            problems.append(f"{change.path}: is not a node edited in place under {tree_root}")
            continue
        base_text, head_text = read_file(BASE, change.path), read_file(HEAD, change.path)
        base = read_frontmatter(base_text) if base_text is not None else None
        head = read_frontmatter(head_text) if head_text is not None else None
        if base is None or head is None:
            problems.append(f"{change.path}: is not a node present and readable on both sides")
        elif base[1] != head[1]:
            problems.append(f"{change.path}: changes the node's text")
        else:
            problems += _problems_in_one_node(change.path, base[0], head[0], reply)
    return problems
