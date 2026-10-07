"""The body of a fake `gh project ...`: a JSON file (FAKE_GH_STATE) is the whole of GitHub.

Written to a directory first in PATH by `board_helpers.install_fake_gh`; every call is appended to
the state's `calls`, so a test can say what was read and what was changed.
"""

import json
import os
import sys

STATE_PATH = os.environ["FAKE_GH_STATE"]
with open(STATE_PATH) as handle:
    state = json.load(handle)
argv = sys.argv[1:]
state["calls"].append(argv)


def option(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def save():
    with open(STATE_PATH, "w") as handle:
        json.dump(state, handle)


def finish(payload=None):
    save()
    if payload is not None:
        print(json.dumps(payload))
    sys.exit(0)


def fail(message):
    save()
    print(message, file=sys.stderr)
    sys.exit(1)


assert argv[0] == "project", argv
verb = argv[1]
if verb == "list":
    finish({"projects": state["projects"]})
if verb == "create":
    project = {
        "number": len(state["projects"]) + 1,
        "id": f"PVT_{len(state['projects']) + 1}",
        "title": option("--title"),
    }
    state["projects"].append(project)
    finish(project)
if verb == "view":
    found = [p for p in state["projects"] if str(p["number"]) == argv[2]]
    finish(found[0]) if found else fail("no such project")
if verb == "field-list":
    finish({"fields": state["fields"]})
if verb == "field-create":
    field = {
        "id": f"PVTF_{len(state['fields']) + 1}",
        "name": option("--name"),
        "type": "ProjectV2Field",
        "dataType": option("--data-type"),
    }
    state["fields"].append(field)
    finish(field)
if verb == "item-list":
    finish({"items": state["items"]})
if verb == "item-create":
    count = len(state["items"]) + 1
    item = {
        "id": f"PVTI_{count}",
        "title": option("--title"),
        "type": "DRAFT_ISSUE",
        "content": {
            "id": f"DI_{count}",
            "type": "DraftIssue",
            "title": option("--title"),
            "body": option("--body"),
        },
    }
    state["items"].append(item)
    finish(item)
if verb == "item-edit":
    item_id = option("--id")
    if "--field-id" in argv:
        assert item_id.startswith("PVTI_") and option("--project-id"), argv
        name = next(f["name"] for f in state["fields"] if f["id"] == option("--field-id"))
        item = next(i for i in state["items"] if i["id"] == item_id)
        value = option("--text") if "--text" in argv else float(option("--number"))
        item[name[0].lower() + name[1:]] = value
        finish({})
    assert item_id.startswith("DI_"), "a draft's title and body are edited by its draft id"
    item = next(i for i in state["items"] if i["content"]["id"] == item_id)
    item["title"] = item["content"]["title"] = option("--title", item["title"])
    item["content"]["body"] = option("--body", item["content"]["body"])
    finish({})
fail(f"fake gh: unhandled {argv}")
