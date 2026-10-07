"""The bench's three sessions of eight actions (`measure.py main`)."""

from __future__ import annotations

Step = tuple[str, dict]

# Three sessions over one store. Session 1 starts on an empty store and establishes facts; 2 and 3
# must find them, extend them and report them correctly. Each session mixes every action, the gap one
# (`export_csv`, whose node does not describe exporting) among them, and each carries requests the
# rules must refuse.
SESSIONS: dict[str, list[Step]] = {
    "s1": [
        (
            "create_ticket",
            {"title": "Printer on floor 2 jams on every duplex job", "priority": "high"},
        ),
        ("create_ticket", {"title": "Wifi drops in meeting room B", "priority": "normal"}),
        ("create_ticket", {"title": "Add a dark theme to the dashboard", "priority": "low"}),
        ("change_status", {"id": "T-1", "status": "in_progress"}),
        ("change_status", {"id": "T-2", "status": "resolved", "note": "Rebooted the access point"}),
        ("show_board", {}),
        ("board_report", {}),
        ("export_csv", {}),
    ],
    "s2": [
        ("show_board", {}),
        ("change_status", {"id": "T-1", "status": "resolved", "note": "Replaced the fuser unit"}),
        ("create_ticket", {"title": "Rotate the shared mailbox password", "priority": "high"}),
        ("change_status", {"id": "T-2", "status": "in_progress"}),
        ("change_status", {"id": "T-3", "status": "in_progress"}),
        ("change_status", {"id": "T-9", "status": "in_progress"}),
        ("board_report", {}),
        ("export_csv", {}),
    ],
    "s3": [
        ("board_report", {}),
        ("create_ticket", {"title": "Archive last year's invoices", "priority": "low"}),
        ("change_status", {"id": "T-4", "status": "in_progress"}),
        ("change_status", {"id": "T-1", "status": "in_progress"}),
        (
            "change_status",
            {"id": "T-3", "status": "resolved", "note": "Dark theme shipped behind a flag"},
        ),
        ("show_board", {}),
        ("export_csv", {}),
        ("board_report", {}),
    ],
}
SESSION_NUMBERS = {"1": "s1", "2": "s2", "3": "s3"}
