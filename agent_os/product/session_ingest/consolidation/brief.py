"""The first message of each turn: the drafter's and the reviewer's."""

from __future__ import annotations

from agent_os.product.session_ingest.consolidation.answer import Draft


def drafter_brief(*, node_id: str, job_body: str, definition: str, mentions: str) -> str:
    return (
        f"Consolidate the use case `{node_id}`.\n\n"
        f"## The use case file as it stands\n\n{definition}\n"
        f"## The job issue (the decisions of the amendment and the owner's words)\n\n{job_body}\n\n"
        f"## Lines outside the tree that name `{node_id}`\n\n{mentions or '(none)'}\n"
    )


def reviewer_brief(*, node_id: str, job_body: str, before: str, draft: Draft) -> str:
    tests = "\n".join(draft.obsolete_tests) or "(none proposed)"
    return (
        f"Review the draft consolidation of `{node_id}`.\n\n"
        f"## The use case before\n\n{before}\n"
        f"## The draft\n\n{draft.definition}\n"
        f"## The job issue (the decisions of the amendment and the owner's words)\n\n{job_body}\n\n"
        f"## Tests the draft proposes to delete or adjust\n\n{tests}\n"
    )
