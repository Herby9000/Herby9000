"""Read-only Attio fixture adapter."""
from __future__ import annotations

import re
from typing import Any


class ReadOnlyViolation(ValueError):
    """Raised when a request could mutate Attio."""


class ReadOnlyPolicy:
    _QUERY_PATHS = (
        re.compile(r"^/v2/lists/[^/]+/entries/query$"),
        re.compile(r"^/v2/objects/[^/]+/records/query$"),
    )

    def validate(self, method: str, path: str) -> None:
        method = method.upper()
        clean_path = path.split("?", 1)[0]
        if method == "GET":
            return
        if method == "POST" and any(pattern.fullmatch(clean_path) for pattern in self._QUERY_PATHS):
            return
        raise ReadOnlyViolation(f"blocked non-read request: {method} {clean_path}")


def provenance(source_type: str, source_id: str, observed_at: str | None = None, confidence: str = "high") -> dict[str, Any]:
    return {
        "source_type": source_type,
        "source_id": source_id,
        "observed_at": observed_at,
        "confidence": confidence,
    }


class AttioCollector:
    def __init__(self, primary_list_id: str):
        if not primary_list_id:
            raise ValueError("primary_list_id is required")
        self.primary_list_id = primary_list_id

    def collect(self, payload: dict[str, Any]) -> dict[str, Any]:
        primary_lists = [item for item in payload.get("lists", []) if item.get("id") == self.primary_list_id]
        if not primary_lists:
            raise ValueError(f"primary Attio list not found: {self.primary_list_id}")
        primary_list = dict(primary_lists[0])
        list_attributes = [dict(item) for item in payload.get("list_attributes", {}).get(self.primary_list_id, [])]
        entries = payload.get("list_entries", {}).get(self.primary_list_id, [])
        records = {record["id"]: record for record in payload.get("records", [])}
        pipeline = []
        member_ids = set()
        for entry in entries:
            record_id = entry.get("record_id")
            member_ids.add(record_id)
            record = records.get(record_id, {})
            pipeline.append({
                "record_id": record_id,
                "name": record.get("name"),
                "email": record.get("email"),
                "stage": {
                    "value": entry.get("stage"),
                    "provenance": provenance("attio_list_entry", entry["id"], entry.get("updated_at")),
                },
            })
        candidates = [
            {
                "record_id": record["id"],
                "name": record.get("name"),
                "email": record.get("email"),
                "candidate_only": True,
                "provenance": provenance("attio_record", record["id"], record.get("updated_at"), "medium"),
            }
            for record in payload.get("records", [])
            if record.get("id") not in member_ids and record.get("object") in {"people", "companies"}
        ]
        relevant_ids = member_ids
        output: dict[str, Any] = {
            "primary_list": primary_list,
            "list_attributes": list_attributes,
            "pipeline": pipeline,
            "potential_prospects": candidates,
        }
        for key in ("tasks", "notes", "meetings"):
            output[key] = [dict(item) for item in payload.get(key, []) if item.get("record_id") in relevant_ids]
        return output
