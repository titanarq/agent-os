"""A reference executor: the operations of `operations.py` applied to any store that has five
methods, all-or-nothing as far as validation can see.

An app in another stack re-implements this in twenty lines; an app in Python can use it as it is.
The store provides:

    exists(collection, id) -> bool            put(collection, id, document)
    update(collection, id, changes)           delete(collection, id)
    next_number(counter) -> int               transaction() -> a context manager that holds
                                              the store's lock (and commits) for the whole plan

Every operation is checked against the store as the plan would leave it BEFORE anything is written,
so a plan that cannot apply changes nothing and burns no counter. A crash in the middle of the
writes is the store's to survive (a database transaction does; a file store cannot).
"""

from __future__ import annotations

from typing import Protocol

from agent_os.product.puntal.fast.operations import fill_bindings


class OperationStore(Protocol):
    def exists(self, collection: str, identifier: str) -> bool: ...
    def put(self, collection: str, identifier: str, document: dict) -> None: ...
    def update(self, collection: str, identifier: str, changes: dict) -> None: ...
    def delete(self, collection: str, identifier: str) -> None: ...
    def next_number(self, counter: str) -> int: ...
    def transaction(self): ...


def _placeholder_free(identifier: str) -> bool:
    return "{{" not in identifier


def _refusals(store: OperationStore, operations: list[dict]) -> list[str]:
    """What would fail, simulating existence over the plan. An id that is still a placeholder is
    skipped: it is allocated, so it cannot be missing."""
    present: dict[tuple[str, str], bool] = {}

    def is_there(collection: str, identifier: str) -> bool:
        key = (collection, identifier)
        return present[key] if key in present else store.exists(collection, identifier)

    errors = []
    for position, operation in enumerate(operations, start=1):
        kind = operation["op"]
        if kind == "allocate":
            continue
        key = (operation["collection"], operation["id"])
        if kind == "put":
            present[key] = True
        elif not _placeholder_free(operation["id"]):
            continue
        elif not is_there(*key):
            errors.append(f"operation {position} ({kind}): there is no {key[0]}/{key[1]}")
        elif kind == "delete":
            present[key] = False
    return errors


def apply_operations(store: OperationStore, operations: list[dict]) -> dict:
    """The executor's verdict (`fast/executor.py`) for `operations` applied to `store`."""
    with store.transaction():
        errors = _refusals(store, operations)
        if errors:
            return {"ok": False, "errors": errors}
        bindings: dict = {}
        for operation in operations:
            kind = operation["op"]
            if kind == "allocate":
                bindings[operation["bind"]] = store.next_number(operation["counter"])
                continue
            filled = fill_bindings(operation, bindings)
            if kind == "put":
                store.put(filled["collection"], filled["id"], filled["document"])
            elif kind == "update":
                store.update(filled["collection"], filled["id"], filled["changes"])
            else:
                store.delete(filled["collection"], filled["id"])
    return {"ok": True, "bindings": bindings}
