"""The one module that runs `gh`: a GitHub Project (v2) as a small client.

Every call is `gh project ... --format json` against the owner in the config. Nothing here knows
the tree; a failing `gh` is a `BoardError` carrying its own message, never a guess.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

ITEM_LIST_LIMIT = "1000"


class BoardError(Exception):
    """`gh` is missing, refused, or answered something that is not JSON."""


class GhProjectClient:
    def __init__(self, owner: str):
        self.owner = owner

    def _gh(self, *arguments: str) -> Any:
        try:
            completed = subprocess.run(
                ["gh", "project", *arguments], capture_output=True, text=True, check=False
            )
        except FileNotFoundError as error:
            raise BoardError(
                "`gh` is not on PATH; the progress board needs the GitHub CLI"
            ) from error
        if completed.returncode != 0:
            raise BoardError(
                f"`gh project {' '.join(arguments[:1])}` failed: {completed.stderr.strip()}"
            )
        try:
            return json.loads(completed.stdout) if completed.stdout.strip() else {}
        except json.JSONDecodeError as error:
            raise BoardError(f"`gh project {arguments[0]}` did not answer JSON") from error

    def list_projects(self) -> list[dict]:
        return self._gh("list", "--owner", self.owner, "--format", "json").get("projects", [])

    def create_project(self, title: str) -> dict:
        return self._gh("create", "--owner", self.owner, "--title", title, "--format", "json")

    def view_project(self, number: int) -> dict:
        return self._gh("view", str(number), "--owner", self.owner, "--format", "json")

    def list_fields(self, number: int) -> list[dict]:
        return self._gh("field-list", str(number), "--owner", self.owner, "--format", "json").get(
            "fields", []
        )

    def create_field(self, number: int, name: str, data_type: str) -> dict:
        return self._gh(
            "field-create", str(number), "--owner", self.owner, "--name", name,
            "--data-type", data_type, "--format", "json",
        )  # fmt: skip

    def list_items(self, number: int) -> list[dict]:
        return self._gh(
            "item-list", str(number), "--owner", self.owner, "--limit", ITEM_LIST_LIMIT,
            "--format", "json",
        ).get("items", [])  # fmt: skip

    def create_item(self, number: int, title: str, body: str) -> dict:
        return self._gh(
            "item-create", str(number), "--owner", self.owner, "--title", title, "--body", body,
            "--format", "json",
        )  # fmt: skip

    def edit_draft(self, draft_id: str, title: str, body: str) -> None:
        self._gh("item-edit", "--id", draft_id, "--title", title, "--body", body)

    def set_text_field(self, project_id: str, item_id: str, field_id: str, text: str) -> None:
        self._gh(
            "item-edit", "--id", item_id, "--project-id", project_id, "--field-id", field_id,
            "--text", text,
        )  # fmt: skip
