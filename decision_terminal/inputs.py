"""Normalize local, trusted-upstream JSON snapshots without external access."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Union

JsonSource = Union[str, Path, Dict[str, Any]]


def _payload(source: JsonSource) -> Dict[str, Any]:
    if isinstance(source, dict):
        return source
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _candidate(value: Any, provenance: Dict[str, Any]) -> Dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    candidate = copy.deepcopy(value)
    candidate["provenance"] = copy.deepcopy(provenance)
    return candidate


def normalize_gmail(source: JsonSource) -> List[Dict[str, Any]]:
    """Normalize compact Gmail thread snapshots supplied by a trusted reader."""
    output = []
    for thread in _payload(source).get("threads", []):
        thread_id = str(thread["id"])
        source_url = thread.get("web_url")
        candidates = []
        for message in thread.get("messages", []):
            message_id = str(message["id"])
            provenance = {
                "source_type": "gmail_message",
                "source_id": f"{thread_id}/{message_id}",
            }
            if source_url:
                provenance["source_url"] = source_url
            if message.get("timestamp"):
                provenance["observed_at"] = message["timestamp"]
            normalized = _candidate(message.get("candidate"), provenance)
            if normalized:
                candidates.append(normalized)
        output.append({
            "source_type": "gmail_thread",
            "source_id": thread_id,
            "subject": thread.get("subject", ""),
            "candidates": candidates,
            "provenance": {
                "source_type": "gmail_thread",
                "source_id": thread_id,
                **({"source_url": source_url} if source_url else {}),
            },
        })
    return output


def normalize_calendar(source: JsonSource) -> List[Dict[str, Any]]:
    """Normalize compact Calendar event snapshots supplied by a trusted reader."""
    output = []
    for event in _payload(source).get("events", []):
        event_id = str(event["id"])
        provenance = {"source_type": "calendar_event", "source_id": event_id}
        if event.get("html_link"):
            provenance["source_url"] = event["html_link"]
        if event.get("updated") or event.get("start"):
            provenance["observed_at"] = event.get("updated") or event.get("start")
        candidate = _candidate(event.get("candidate"), provenance)
        output.append({
            "source_type": "calendar_event",
            "source_id": event_id,
            "title": event.get("title", ""),
            "start": event.get("start"),
            "candidates": [candidate] if candidate else [],
            "provenance": copy.deepcopy(provenance),
        })
    return output


def normalize_business_notes(source: JsonSource) -> List[Dict[str, Any]]:
    """Normalize only explicitly allowlisted business-note excerpts."""
    output = []
    for note in _payload(source).get("notes", []):
        if note.get("allowlisted") is not True:
            continue
        note_id = str(note["id"])
        candidate_value = note.get("candidate")
        tags = note.get("tags", [])
        if "first_spike_private_action" in tags:
            kind = candidate_value.get("kind") if isinstance(candidate_value, dict) else None
            if kind not in {"decision", "commitment"}:
                raise ValueError("first_spike_private_action requires a private decision or commitment")
        provenance = {"source_type": "business_note", "source_id": note_id}
        if note.get("source_url"):
            provenance["source_url"] = note["source_url"]
        if note.get("updated"):
            provenance["observed_at"] = note["updated"]
        candidate = _candidate(candidate_value, provenance)
        output.append({
            "source_type": "business_note",
            "source_id": note_id,
            "excerpt": note.get("excerpt", ""),
            "tags": list(tags),
            "candidates": [candidate] if candidate else [],
            "provenance": copy.deepcopy(provenance),
        })
    return output
