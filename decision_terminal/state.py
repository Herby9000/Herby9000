"""Private JSON state for Decision Terminal items."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Iterable

_ALLOWED = {
    "candidate": {"confirmed"},
    "confirmed": {"active"},
    "active": {"waiting", "delegated", "snoozed", "completed", "cancelled"},
    "waiting": {"active", "completed", "cancelled"},
    "delegated": {"active", "completed", "cancelled"},
    "snoozed": {"active", "completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


class DecisionState:
    """A state file whose records survive absent source snapshots."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        if self.path.exists():
            self._document = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._document = {"version": 1, "items": {}}
        if self._document.get("version") != 1 or not isinstance(self._document.get("items"), dict):
            raise ValueError("unsupported Decision Terminal state document")

    def synchronize(self, candidates: Iterable[Dict[str, Any]]) -> None:
        items = self._document["items"]
        for record in items.values():
            record["present_in_latest_snapshot"] = False
        for candidate in candidates:
            item_id = candidate["id"]
            if item_id not in items:
                items[item_id] = {
                    "id": item_id,
                    "status": "candidate",
                    "candidate": copy.deepcopy(candidate),
                    "present_in_latest_snapshot": True,
                    "history": [],
                    "corrections": {},
                    "details_requested": False,
                }
            else:
                items[item_id]["candidate"] = copy.deepcopy(candidate)
                items[item_id]["present_in_latest_snapshot"] = True
        self.save()

    def get(self, item_id: str) -> Dict[str, Any]:
        try:
            return copy.deepcopy(self._document["items"][item_id])
        except KeyError as error:
            raise KeyError(f"unknown Decision Terminal item: {item_id}") from error

    def items_for_edition(self) -> list[Dict[str, Any]]:
        """Return non-terminal items with local corrections overlaid."""
        output = []
        for record in self._document["items"].values():
            if record["status"] in {"completed", "cancelled"}:
                continue
            item = copy.deepcopy(record["candidate"])
            item.update(record.get("corrections", {}))
            item["status"] = record["status"]
            output.append(item)
        return sorted(output, key=lambda item: (item["queue"], item["id"]))

    def transition(self, item_id: str, target: str, metadata: Dict[str, Any] | None = None) -> None:
        record = self._record(item_id)
        current = record["status"]
        if target not in _ALLOWED.get(current, set()):
            raise ValueError(f"invalid transition: {current} -> {target}")
        event = {"from": current, "to": target}
        if metadata:
            event["metadata"] = copy.deepcopy(metadata)
        record["status"] = target
        record["history"].append(event)
        self.save()

    def correct(self, item_id: str, field: str, value: str) -> None:
        allowed = {"summary", "why_it_matters", "proposed_next_action", "owner", "due_date", "review_date", "confidence", "queue"}
        if field not in allowed or not value.strip():
            raise ValueError(f"unsupported correction field: {field}")
        self._record(item_id)["corrections"][field] = value.strip()
        self.save()

    def request_details(self, item_id: str) -> None:
        self._record(item_id)["details_requested"] = True
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.path)

    def _record(self, item_id: str) -> Dict[str, Any]:
        try:
            return self._document["items"][item_id]
        except KeyError as error:
            raise KeyError(f"unknown Decision Terminal item: {item_id}") from error
