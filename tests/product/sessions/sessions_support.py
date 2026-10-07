"""Shared helpers of the session tests: node files, a config of the test's own, and a fake `gh`.

Imported by name (`from sessions_support import ...`), the way `conftest` is. Nothing here reaches
the network or a backend: `gh` is a script first in `PATH` that answers from a table.
"""

from __future__ import annotations

import json
import pathlib
import shlex
import stat

import yaml
from conftest import EXAMPLE_CONFIG

OWNER_LOGIN = "the-owner"
TREE_ROOT = "product"


def write_node(root: pathlib.Path, node_id: str, node_type: str, **fields) -> pathlib.Path:
    frontmatter = {
        "id": node_id,
        "type": node_type,
        "title": f"Title of {node_id}",
        "sources": ["owner brief"],
    }
    if node_type == "goal":
        frontmatter["verification"] = [{"judge": f"An agent finds that {node_id} holds."}]
    else:
        frontmatter["mechanism"] = "pending"
    frontmatter.update(fields)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{node_id}.md"
    dumped = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
    path.write_text(f"---\n{dumped}---\nDescription of {node_id}.\n", encoding="utf-8")
    return path


def what_question(question: str, default: str, **fields) -> dict:
    return {
        "kind": "question",
        "question": question,
        "outcome": "open",
        "date": "2026-10-01",
        "scope": "what",
        "default_answer": default,
        **fields,
    }


def config_file(tmp_path: pathlib.Path, **tree_keys) -> pathlib.Path:
    data = yaml.safe_load(EXAMPLE_CONFIG.read_text())
    data["project"]["human_login"] = OWNER_LOGIN
    data["tree"] = {"root": TREE_ROOT, **tree_keys}
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


FAKE_GH = """#!/usr/bin/env python3
import json, sys
routes = json.load(open({routes!r}))
joined = " ".join(sys.argv[1:])
with open({calls!r}, "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
for key in sorted(routes, key=lambda k: (k.startswith("="), len(k)), reverse=True):
    if (key[1:] in sys.argv[1:]) if key.startswith("=") else (key in joined):
        answer = routes[key]
        if answer is None:
            sys.stderr.write("HTTP 404: Not Found\\n")
            sys.exit(1)
        sys.stdout.write(answer if isinstance(answer, str) else json.dumps(answer))
        sys.exit(0)
sys.stderr.write("fake gh: no route for " + joined + "\\n")
sys.exit(1)
"""


class FakeGh:
    """`routes` maps a substring of the `gh` arguments to its answer: a JSON value, raw text, or
    None for a 404. A key starting with `=` must equal one whole argument and wins over a substring
    key; otherwise the longest matching key wins. An unrouted call fails loudly."""

    def __init__(self, tmp_path: pathlib.Path, monkeypatch):
        self.routes: dict = {}
        self._routes_file = tmp_path / "gh_routes.json"
        self._calls_file = tmp_path / "gh_calls.log"
        directory = tmp_path / "fake-gh-bin"
        directory.mkdir()
        script = directory / "gh"
        script.write_text(
            FAKE_GH.format(routes=str(self._routes_file), calls=str(self._calls_file))
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        monkeypatch.setenv("PATH", f"{directory}:{__import__('os').environ['PATH']}")
        monkeypatch.setenv("AGENT_OS_GH_REPO", "acme/widgets")
        monkeypatch.setenv("WORKER_CACHE_DIR", str(tmp_path / "cache"))
        self.route()

    def route(self, **more) -> None:
        self.routes.update(more)
        self._routes_file.write_text(json.dumps(self.routes))

    def set_route(self, key: str, answer) -> None:
        self.routes[key] = answer
        self._routes_file.write_text(json.dumps(self.routes))

    def calls(self) -> list[list[str]]:
        if not self._calls_file.exists():
            return []
        return [json.loads(line) for line in self._calls_file.read_text().splitlines()]


def quoted(path: pathlib.Path) -> str:
    return shlex.quote(str(path))
