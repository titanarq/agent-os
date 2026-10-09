"""`agent-os-sessions`: the judgments log, the question session, the guard on the what and the
ingestion of the owner's test sessions (`docs/AGENT_OS.md` §4.10, §4.11).

    agent-os-sessions judgment --role R --kind K --decision D --scope what|how [--node N]
        [--model M] [--cli-version V] [--prompt-file F]      # appends to .cache/judgments/
    agent-os-sessions outcome JUDGMENT_ID confirmed|reversed|reclaimed --source S [--detail D]
    agent-os-sessions open [--root DIR] [--dry-run]    # ONE issue freezing what waits for the owner
    agent-os-sessions answers SESSION [--json]         # the owner's replies, parsed
    agent-os-sessions apply SESSION [--root DIR]       # answers and reclaims into the working tree
    agent-os-sessions guard-what PR                    # exit 1: the PR touches the owner's what
    agent-os-sessions verify-answer PR --session SESSION   # exit 0: the PR is exactly the answers
    agent-os-sessions test-ingest [--apply]            # closed test sessions into tree and backlog

Exit status: 0 on success, 1 on a refusal (one line on stderr, or the lines the command prints),
2 on a usage error.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys
from collections.abc import Sequence

from agent_os import lib
from agent_os.cli import host_root
from agent_os.issues import repo_name
from agent_os.product.records import record_versions
from agent_os.product.session_ingest import cli as test_ingest_cli
from agent_os.product.sessions import github, judgments, session_log
from agent_os.product.sessions.batch import build_batch
from agent_os.product.sessions.render import (
    read_frozen_batch,
    render_session_body,
    session_title,
)
from agent_os.product.sessions.reply import resolve_reply
from agent_os.product.sessions.transcription import verify_transcription
from agent_os.product.sessions.what_guard import find_what_touches
from agent_os.product.sessions.writeback import (
    WritebackError,
    answer_question,
    raise_reclaimed_question,
)
from agent_os.product.tree.cli import _resolve_root as resolve_tree_root
from agent_os.product.tree.loader import load_tree

PROGRAM = "agent-os-sessions"


class RefusedError(Exception):
    """A command that cannot go on; its message is the one line printed on stderr."""


def cache_directory() -> pathlib.Path:
    override = os.environ.get("WORKER_CACHE_DIR")
    return pathlib.Path(override) if override else host_root() / ".cache"


def _config(config_path) -> lib.AgentsConfig:
    try:
        return lib.load_agents_config(config_path or lib.DEFAULT_AGENTS_CONFIG)
    except lib.CONFIG_LOAD_ERRORS as error:
        raise RefusedError(
            lib.config_load_failure(error, config_path or lib.DEFAULT_AGENTS_CONFIG)
        ) from error


def _record_judgment(args: argparse.Namespace, config_path) -> int:
    prompt_text = pathlib.Path(args.prompt_file).read_text() if args.prompt_file else ""
    versions = record_versions(
        model=args.model,
        cli_version=args.cli_version,
        prompt_text=prompt_text,
        agent_os_dir=lib.AGENT_OS_DIR,
    )
    print(
        judgments.record_judgment(
            cache_directory(),
            role=args.role,
            kind=args.kind,
            node=args.node,
            decision=args.decision,
            scope=args.scope,
            versions=versions,
        )
    )
    return 0


def _record_outcome(args: argparse.Namespace, config_path) -> int:
    judgments.record_outcome(
        cache_directory(),
        judgment_id=args.judgment_id,
        outcome=args.outcome,
        source=args.source,
        detail=args.detail,
    )
    return 0


def _open(args: argparse.Namespace, config_path) -> int:
    config = _config(config_path)
    tree = load_tree(resolve_tree_root(args.root, config_path))
    cache = cache_directory()
    moment = datetime.datetime.now(datetime.UTC)
    batch = build_batch(
        tree, judgments.judgments_since(cache, session_log.last_session_opened_at(cache))
    )
    if batch.is_empty:
        print("nothing is waiting for the owner: no session opened")
        return 0
    body = render_session_body(batch)
    if args.dry_run:
        print(body, end="")
        return 0
    number = github.open_session_issue(
        repo_name(),
        session_title(moment.date().isoformat()),
        body,
        [config.project.labels.blocked_on_human],
    )
    session_log.record_session(
        cache,
        issue=number,
        opened_at=moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        questions=len(batch.questions),
        digest_entries=len(batch.digest),
    )
    print(f"opened session issue #{number}: {len(batch.questions)} question(s)")
    return 0


def _resolved_replies(config: lib.AgentsConfig, session: int):
    repo = repo_name()
    try:
        frozen = read_frozen_batch(github.issue_body(repo, session))
    except ValueError as error:
        raise RefusedError(f"#{session}: {error}") from error
    comments = github.owner_comments(repo, session, config.project)
    return resolve_reply(comments, frozen)


def _answers(args: argparse.Namespace, config_path) -> int:
    reply = _resolved_replies(_config(config_path), args.session)
    if args.json:
        print(
            json.dumps(
                reply.__dict__, default=lambda value: value.__dict__, ensure_ascii=False, indent=2
            )
        )
        return 0
    for answer in reply.answers:
        origin = "default accepted" if answer.accepted_default else "answered"
        print(f"{answer.number}. {answer.node_id}: {origin}: {answer.answer}")
    for number in reply.declined_numbers:
        print(f"{number}. declined without another answer: stays open")
    for entry in reply.reclaimed_digest_entries:
        print(f"reclaim {entry['number']}: {entry['decision']}")
    for problem in reply.problems:
        print(f"problem: {problem}")
    return 0


def _apply(args: argparse.Namespace, config_path) -> int:
    reply = _resolved_replies(_config(config_path), args.session)
    tree = load_tree(resolve_tree_root(args.root, config_path))
    today = datetime.datetime.now(datetime.UTC).date()
    changed: list[pathlib.Path] = []
    try:
        for answer in reply.answers:
            changed.append(answer_question(tree, answer.node_id, answer.question, answer.answer))
        for entry in reply.reclaimed_digest_entries:
            if entry["node"]:
                changed.append(
                    raise_reclaimed_question(
                        tree, entry["node"], entry["decision"], raised_on=today
                    )
                )
    except WritebackError as error:
        raise RefusedError(str(error)) from error
    for entry in reply.reclaimed_digest_entries:
        judgments.record_outcome(
            cache_directory(),
            judgment_id=entry["judgment_id"],
            outcome="reclaimed",
            source=f"question session #{args.session}",
            detail="the owner took the decision back",
        )
    for path in dict.fromkeys(changed):
        print(f"wrote {path}")
    for problem in reply.problems:
        print(f"problem: {problem}", file=sys.stderr)
    return 0


def _test_ingest(args: argparse.Namespace, config_path) -> int:
    return test_ingest_cli.run_test_ingest(
        args,
        _config(config_path),
        cache=cache_directory(),
        tree_root=resolve_tree_root(args.root, config_path),
    )


def _guard_what(args: argparse.Namespace, config_path) -> int:
    config = _config(config_path)
    repo = repo_name()
    touches = find_what_touches(
        github.pull_request_changes(repo, args.pull_request),
        tree_root=config.tree.root,
        owner_only_paths=config.tree.owner_only_paths,
        read_file=github.pull_request_file_reader(repo, args.pull_request),
    )
    for touch in touches:
        print(f"{touch.path}: {touch.reason}")
    return 1 if touches else 0


def _verify_answer(args: argparse.Namespace, config_path) -> int:
    config = _config(config_path)
    repo = repo_name()
    problems = verify_transcription(
        github.pull_request_changes(repo, args.pull_request),
        tree_root=config.tree.root,
        read_file=github.pull_request_file_reader(repo, args.pull_request),
        reply=_resolved_replies(config, args.session),
    )
    for problem in problems:
        print(problem)
    return 1 if problems else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("judgment", help="record a judgment taken without the owner")
    p.add_argument("--role", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--decision", required=True)
    p.add_argument("--scope", required=True, choices=judgments.SCOPES)
    p.add_argument("--node")
    p.add_argument("--model")
    p.add_argument("--cli-version")
    p.add_argument("--prompt-file", help="the exact prompt that ran, for its digest")
    p.set_defaults(handler=_record_judgment)

    p = sub.add_parser("outcome", help="record what later came of a judgment")
    p.add_argument("judgment_id")
    p.add_argument("outcome", choices=judgments.OUTCOMES)
    p.add_argument("--source", required=True)
    p.add_argument("--detail")
    p.set_defaults(handler=_record_outcome)

    p = sub.add_parser("open", help="open the question session issue")
    p.add_argument("--root", help="the tree directory (default: `tree.root`)")
    p.add_argument("--dry-run", action="store_true", help="print the body, open nothing")
    p.set_defaults(handler=_open)

    p = sub.add_parser("answers", help="the owner's replies, parsed")
    p.add_argument("session", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=_answers)

    p = sub.add_parser("apply", help="write the answers and reclaims into the tree")
    p.add_argument("session", type=int)
    p.add_argument("--root", help="the tree directory (default: `tree.root`)")
    p.set_defaults(handler=_apply)

    p = sub.add_parser("guard-what", help="exit 1 when a pull request touches the what")
    p.add_argument("pull_request", type=int)
    p.set_defaults(handler=_guard_what)

    p = sub.add_parser("verify-answer", help="exit 0 when a pull request transcribes the answers")
    p.add_argument("pull_request", type=int)
    p.add_argument("--session", type=int, required=True)
    p.set_defaults(handler=_verify_answer)

    test_ingest_cli.add_parser(sub, handler=_test_ingest)
    return parser


def main(
    argv: Sequence[str] | None = None, *, config_path: pathlib.Path | str | None = None
) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args, config_path)
    except (RefusedError, judgments.JudgmentError, test_ingest_cli.IngestRefused) as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        return 1
