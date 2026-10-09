"""`agent-os-sessions test-ingest`: the closed test sessions of the owner, carried into the tree and
the backlog.

    agent-os-sessions test-ingest [--root DIR] [--sessions-dir DIR] [--session ID] [--apply]
        # default: print the plan of every closed session not yet ingested, write nothing
        # --apply: write the answers and the acceptances into the working tree, open the rework
        #          issues, and remember the session as ingested (a pull request carries the tree)
        # --session ID: plan (or apply) that one session again, ingested or not

This module owns the command's arguments and its run; `agent_os.product.sessions.cli` registers it
and gives it what that CLI already resolves (the config, the cache, the tree root).
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import sys

from agent_os import lib
from agent_os.cli import host_root
from agent_os.issues import type_labels
from agent_os.product.puntal.options import run_dir_for
from agent_os.product.session_ingest.apply import (
    ReworkTicketSettings,
    ReworkTracker,
    apply_session_plan,
)
from agent_os.product.session_ingest.github_tracker import GitHubReworkTracker
from agent_os.product.session_ingest.plan import plan_session
from agent_os.product.session_ingest.registry import ingested_session_ids, record_ingested
from agent_os.product.session_ingest.render import render_plan
from agent_os.product.session_ingest.rework_ticket import ReworkTicketError
from agent_os.product.session_ingest.session_file import (
    ClosedSession,
    SessionFileError,
    read_closed_sessions,
)
from agent_os.product.sessions.writeback import WritebackError
from agent_os.product.tree.loader import load_tree

FEEDBACK_FILE = "feedback.jsonl"


class IngestRefused(Exception):
    """The command cannot go on; the message is the one line printed on stderr."""


def add_parser(sub, *, handler) -> None:
    parser = sub.add_parser(
        "test-ingest", help="carry the closed test sessions into the tree and the backlog"
    )
    parser.add_argument("--root", help="the tree directory (default: `tree.root`)")
    parser.add_argument("--sessions-dir", help="default: `tree.test_sessions_dir`")
    parser.add_argument("--session", help="this session only, even when it was ingested before")
    parser.add_argument("--apply", action="store_true", help="carry the plan out (default: print)")
    parser.set_defaults(handler=handler)


def build_tracker() -> ReworkTracker:
    return GitHubReworkTracker()


def _sessions_directory(args: argparse.Namespace, config: lib.AgentsConfig) -> pathlib.Path:
    configured = pathlib.Path(args.sessions_dir or config.tree.test_sessions_dir)
    return configured if configured.is_absolute() else host_root() / configured


def _ticket_settings(config: lib.AgentsConfig) -> ReworkTicketSettings:
    if not config.tree.ticket_budget_class:
        raise IngestRefused(
            "tree.ticket_budget_class is empty: a rework ticket names the worker class it "
            "needs, and the mechanism does not invent one"
        )
    types = type_labels(config.project)
    return ReworkTicketSettings(
        budget_class=config.tree.ticket_budget_class,
        task_classes=config.classes,
        labels=[label for label in (types.get("bug") or types.get("task"),) if label]
        + config.tree.ticket_labels,
        tree_root=config.tree.root,
    )


def _sessions_to_ingest(
    sessions: list[ClosedSession], already: set[str], only: str | None
) -> list[ClosedSession]:
    if only is None:
        return [session for session in sessions if session.id not in already]
    chosen = [session for session in sessions if session.id == only]
    if not chosen:
        raise IngestRefused(f"no closed test session {only!r} in the sessions directory")
    return chosen


def run_test_ingest(
    args: argparse.Namespace,
    config: lib.AgentsConfig,
    *,
    cache: pathlib.Path,
    tree_root: pathlib.Path,
) -> int:
    try:
        sessions, file_problems = read_closed_sessions(_sessions_directory(args, config))
    except SessionFileError as error:
        raise IngestRefused(f"{error} (key `tree.test_sessions_dir`)") from error
    pending = _sessions_to_ingest(sessions, ingested_session_ids(cache), args.session)
    problems = list(file_problems)
    if not pending:
        print("no closed test session is waiting to be ingested")
    settings = (
        _ticket_settings(config)
        if args.apply and any(c.verdict == "reject" for s in pending for c in s.cases)
        else None
    )
    tracker = build_tracker()
    feedback_file = run_dir_for(host_root()) / FEEDBACK_FILE
    written_files: list[pathlib.Path] = []
    for session in pending:
        tree = load_tree(tree_root)
        plan = plan_session(
            session, tree, find_rework_issue=tracker.find, feedback_file=feedback_file
        )
        print("\n".join(render_plan(plan)))
        problems.extend(f"{session.id}: {problem}" for problem in plan.problems)
        if not args.apply:
            continue
        try:
            applied = apply_session_plan(plan, tree, tracker=tracker, settings=settings)
        except (WritebackError, ReworkTicketError) as error:
            raise IngestRefused(f"{session.id}: {error}") from error
        written_files.extend(applied.written_files)
        if not plan.problems:
            record_ingested(
                cache,
                session=session.id,
                ingested_at=datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                answers=applied.answers_written,
                accepted=applied.acceptances_written,
                rework_issues=applied.rework_issues,
            )
    for path in dict.fromkeys(written_files):
        print(f"wrote {path}")
    if written_files:
        print(
            "commit it on a branch with `Node-Change: usage` as the last paragraph, and open the "
            "pull request with `Test-Session: <id>` in its body: it is the owner's word."
        )
    if pending and not args.apply:
        print("dry run: nothing written; --apply carries this out")
    for problem in problems:
        print(f"problem: {problem}", file=sys.stderr)
    return 1 if problems else 0
