#!/usr/bin/env python3
"""The bench's EXECUTOR: the helpdesk app's code that applies a puntal's plan to its JSON store.

    executor.py --dir DIR        reads {"operations": [...]} on stdin, prints the verdict

This is `agent_os.product.puntal.fast.executor`'s interface over `store.py`, through the reference
interpreter. It is also where the app keeps what it DERIVES: the `summary/board` counts are
recomputed here, whenever a plan touched `tickets`, so a puntal never has to recount (and a puntal
that forgot to would not leave the store incoherent).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import domain
from store import Store, StoreError

from agent_os.product.puntal.fast.reference_executor import apply_operations

SUMMARY_COLLECTION, SUMMARY_ID = "summary", "board"
PLACEHOLDER = re.compile(r"\{\{[^{}]*\}\}")


class BenchStoreAdapter:
    """`store.Store` as the five-method target the reference executor wants."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self.touched_tickets = False

    def exists(self, collection: str, identifier: str) -> bool:
        try:
            self.store.get(collection, identifier)
        except StoreError:
            return False
        return True

    def put(self, collection: str, identifier: str, document: dict) -> None:
        self.touched_tickets |= collection == "tickets"
        self.store.put(collection, identifier, document)

    def update(self, collection: str, identifier: str, changes: dict) -> None:
        self.touched_tickets |= collection == "tickets"
        self.store.update(collection, identifier, changes)

    def delete(self, collection: str, identifier: str) -> None:
        self.touched_tickets |= collection == "tickets"
        self.store.delete(collection, identifier)

    def next_number(self, counter: str) -> int:
        return self.store.next_id(counter)

    def transaction(self):
        return self.store._locked()

    def recount_summary(self) -> None:
        tickets = self.store.list("tickets")
        counts = {s: sum(1 for t in tickets if t["status"] == s) for s in domain.STATUSES}
        self.store.put(SUMMARY_COLLECTION, SUMMARY_ID, {**counts, "total": len(tickets)})


def name_errors(store: Store, operations: list[dict]) -> list[str]:
    """A name the file store cannot hold is found before the first write, not in the middle of them."""
    errors = []
    for position, operation in enumerate(operations, start=1):
        for field in ("collection", "id", "counter"):
            value = operation.get(field)
            if isinstance(value, str):
                try:
                    store._check_name(field, PLACEHOLDER.sub("0", value))
                except StoreError as error:
                    errors.append(f"operation {position}: {error}")
    return errors


def execute(store: Store, operations: list[dict]) -> dict:
    adapter = BenchStoreAdapter(store)
    if refused := name_errors(store, operations):
        return {"ok": False, "errors": refused}
    try:
        with adapter.transaction():
            verdict = apply_operations(adapter, operations)
            if verdict["ok"] and adapter.touched_tickets:
                adapter.recount_summary()
    except StoreError as error:
        return {"ok": False, "errors": [f"store: {error}"]}
    return verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="executor.py")
    parser.add_argument("--dir", required=True, help="the store's directory")
    arguments = parser.parse_args(argv)
    try:
        operations = json.load(sys.stdin)["operations"]
    except (ValueError, KeyError, TypeError) as error:
        print(f"executor: unreadable plan ({error})", file=sys.stderr)
        return 2
    print(json.dumps(execute(Store(arguments.dir), operations), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
