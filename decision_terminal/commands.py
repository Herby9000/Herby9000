"""Authenticated, local-only reply command parsing and state application."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from .state import DecisionState

_AUTHORIZED_SENDER = "chtmorris@icloud.com"
_ITEM = r"DT-[A-F0-9]{12}"


class AuthorizationError(PermissionError):
    pass


def parse_commands(body: str, sender: str) -> List[Dict[str, str]]:
    """Parse commands only after exact normalized sender authorization."""
    if sender.strip().lower() != _AUTHORIZED_SENDER:
        raise AuthorizationError("reply sender is not authorized")
    commands = []
    patterns = (
        ("done", re.compile(rf"done\s+({_ITEM})", re.IGNORECASE)),
        ("snooze", re.compile(rf"snooze\s+({_ITEM})\s+until\s+(\d{{4}}-\d{{2}}-\d{{2}})", re.IGNORECASE)),
        ("delegate", re.compile(rf"delegate\s+({_ITEM})\s+to\s+(.+)", re.IGNORECASE)),
        ("waiting", re.compile(rf"waiting\s+({_ITEM})(?:\s+for\s+(.+))?", re.IGNORECASE)),
        ("not_actionable", re.compile(rf"not\s+actionable\s+({_ITEM})", re.IGNORECASE)),
        ("details", re.compile(rf"details\s+({_ITEM})", re.IGNORECASE)),
        ("correct", re.compile(rf"correct\s+({_ITEM})\s+([a-z_]+)=(.+)", re.IGNORECASE)),
    )
    for line_number, raw_line in enumerate(body.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(">"):
            continue
        parsed = None
        for name, pattern in patterns:
            match = pattern.fullmatch(line)
            if not match:
                continue
            parsed = {"command": name, "item_id": match.group(1).upper()}
            if name == "snooze":
                parsed["until"] = match.group(2)
            elif name == "delegate":
                parsed["delegate_to"] = match.group(2).strip()
            elif name == "waiting" and match.group(2):
                parsed["reason"] = match.group(2).strip()
            elif name == "correct":
                parsed["field"] = match.group(2).lower()
                parsed["value"] = match.group(3).strip()
            break
        if parsed is None:
            raise ValueError(f"invalid command on line {line_number}")
        commands.append(parsed)
    return commands


def _activate(state: DecisionState, item_id: str) -> None:
    status = state.get(item_id)["status"]
    if status == "candidate":
        state.transition(item_id, "confirmed")
        status = "confirmed"
    if status == "confirmed":
        state.transition(item_id, "active")
    elif status in {"waiting", "delegated", "snoozed"}:
        state.transition(item_id, "active")


def apply_commands(state: DecisionState, commands: Iterable[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Apply parsed commands to Decision Terminal state and nowhere else."""
    results = []
    for command in commands:
        name = command["command"]
        item_id = command["item_id"]
        if name == "details":
            state.request_details(item_id)
            results.append({"command": name, "item_id": item_id, "status": "details_requested"})
            continue
        if name == "correct":
            state.correct(item_id, command["field"], command["value"])
            results.append({"command": name, "item_id": item_id, "status": "corrected"})
            continue
        _activate(state, item_id)
        if name == "done":
            target, metadata = "completed", None
        elif name == "snooze":
            target, metadata = "snoozed", {"until": command["until"]}
        elif name == "delegate":
            target, metadata = "delegated", {"delegate_to": command["delegate_to"]}
        elif name == "waiting":
            target, metadata = "waiting", ({"reason": command["reason"]} if command.get("reason") else None)
        elif name == "not_actionable":
            target, metadata = "cancelled", {"reason": "not actionable"}
        else:
            raise ValueError(f"unsupported command: {name}")
        state.transition(item_id, target, metadata)
        results.append({"command": name, "item_id": item_id, "status": target})
    return results
