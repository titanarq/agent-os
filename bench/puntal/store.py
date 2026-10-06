#!/usr/bin/env python3
"""The toy bench's persistence API: a JSON document store over a directory, as a command line.

    store.py --dir DIR get COLLECTION ID          the document, as JSON; exit 1 when there is none
    store.py --dir DIR put COLLECTION ID JSON     create or replace a document; prints it
    store.py --dir DIR update COLLECTION ID JSON  merge the fields of JSON into an existing document
    store.py --dir DIR list COLLECTION            every document of the collection, as a JSON array
    store.py --dir DIR delete COLLECTION ID       remove a document; exit 1 when there is none
    store.py --dir DIR next-id COUNTER            increment a counter and print its new value (1, 2...)
    store.py --dir DIR dump                       the whole store as one JSON object

A document is `DIR/<collection>/<id>.json`; counters are `DIR/_counters.json`. Every write goes to a
temporary file in the same directory and is renamed over its target, so a reader never sees half a
document, and the counter is incremented under a lock so two callers never get the same number.
Standard library only: the puntal runs it once per call.

The app's persistence API in a real product is whatever the app has; this one exists so the bench has
state that is real, shared between sessions and checkable.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import pathlib
import re
import sys
import tempfile

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
COUNTERS_FILE = "_counters.json"
LOCK_FILE = ".lock"


class StoreError(Exception):
    pass


def natural_key(identifier: str) -> list:
    """`T-2` before `T-10`: digits compare as numbers."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", identifier)]


class Store:
    def __init__(self, directory: str | os.PathLike) -> None:
        self.directory = pathlib.Path(directory)
        self._lock_depth = 0

    # -- helpers -------------------------------------------------------------------------------
    @staticmethod
    def _check_name(kind: str, value: str) -> str:
        if not NAME_RE.match(value) or value == COUNTERS_FILE.removesuffix(".json"):
            raise StoreError(f"{kind} {value!r} is not a valid name (letters, digits, - and _)")
        return value

    def _path(self, collection: str, identifier: str) -> pathlib.Path:
        return (
            self.directory
            / self._check_name("collection", collection)
            / f"{self._check_name('id', identifier)}.json"
        )

    @contextlib.contextmanager
    def _locked(self):
        """The store's one lock. Re-entrant within this object, so a whole plan can hold it
        (`executor.py`) while the single writes it is made of take it again."""
        if self._lock_depth:
            yield
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / LOCK_FILE).open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1

    @staticmethod
    def _write_atomically(path: pathlib.Path, document: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(descriptor, "w") as handle:
                json.dump(document, handle, indent=1, sort_keys=True)
                handle.write("\n")
            os.replace(temporary, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(temporary)
            raise

    # -- the API -------------------------------------------------------------------------------
    def get(self, collection: str, identifier: str) -> dict:
        path = self._path(collection, identifier)
        try:
            return json.loads(path.read_text())
        except FileNotFoundError:
            raise StoreError(f"not found: {collection}/{identifier}") from None

    def put(self, collection: str, identifier: str, document: dict) -> dict:
        with self._locked():
            self._write_atomically(self._path(collection, identifier), document)
        return document

    def update(self, collection: str, identifier: str, changes: dict) -> dict:
        with self._locked():
            document = self.get(collection, identifier)
            document.update(changes)
            self._write_atomically(self._path(collection, identifier), document)
        return document

    def list(self, collection: str) -> list[dict]:
        folder = self.directory / self._check_name("collection", collection)
        if not folder.is_dir():
            return []
        names = sorted((p.stem for p in folder.glob("*.json")), key=natural_key)
        return [json.loads((folder / f"{name}.json").read_text()) for name in names]

    def delete(self, collection: str, identifier: str) -> None:
        with self._locked():
            path = self._path(collection, identifier)
            try:
                path.unlink()
            except FileNotFoundError:
                raise StoreError(f"not found: {collection}/{identifier}") from None

    def next_id(self, counter: str) -> int:
        with self._locked():
            path = self.directory / COUNTERS_FILE
            counters = json.loads(path.read_text()) if path.is_file() else {}
            counters[self._check_name("counter", counter)] = counters.get(counter, 0) + 1
            self._write_atomically(path, counters)
            return counters[counter]

    def dump(self) -> dict:
        """The whole store: `{collection: {id: document}, "_counters": {...}}`."""
        snapshot: dict = {"_counters": {}}
        if not self.directory.is_dir():
            return snapshot
        for entry in sorted(self.directory.iterdir()):
            if entry.is_dir():
                snapshot[entry.name] = {
                    p.stem: json.loads(p.read_text())
                    for p in sorted(entry.glob("*.json"), key=lambda p: natural_key(p.stem))
                }
        counters = self.directory / COUNTERS_FILE
        if counters.is_file():
            snapshot["_counters"] = json.loads(counters.read_text())
        return snapshot


def _json_argument(text: str) -> dict:
    try:
        value = json.loads(text)
    except ValueError as error:
        raise StoreError(f"not valid JSON ({error}): {text[:80]!r}") from None
    if not isinstance(value, dict):
        raise StoreError("a document is a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="store.py", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--dir", required=True, help="the store's directory")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("get", "delete"):
        sub = commands.add_parser(name)
        sub.add_argument("collection")
        sub.add_argument("id")
    for name in ("put", "update"):
        sub = commands.add_parser(name)
        sub.add_argument("collection")
        sub.add_argument("id")
        sub.add_argument("json")
    commands.add_parser("list").add_argument("collection")
    commands.add_parser("next-id").add_argument("counter")
    commands.add_parser("dump")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = Store(args.dir)
    try:
        if args.command == "get":
            result: object = store.get(args.collection, args.id)
        elif args.command == "put":
            result = store.put(args.collection, args.id, _json_argument(args.json))
        elif args.command == "update":
            result = store.update(args.collection, args.id, _json_argument(args.json))
        elif args.command == "list":
            result = store.list(args.collection)
        elif args.command == "delete":
            store.delete(args.collection, args.id)
            result = {"deleted": f"{args.collection}/{args.id}"}
        elif args.command == "next-id":
            result = store.next_id(args.counter)
        else:
            result = store.dump()
    except StoreError as error:
        print(f"store: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
