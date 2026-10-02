"""Deterministic, conservative reconciliation across normalized sources."""
from __future__ import annotations

import re
from typing import Any

from .attio import provenance

SECTIONS = (
    "upcoming_meetings",
    "follow_ups",
    "untapped_prospects",
    "fundraising_ideas_inputs",
    "conflicts",
    "coverage",
)


def assertion(value: Any, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"value": value, "provenance": evidence}


def _normal_email(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().casefold()
    return candidate if re.fullmatch(r"[^@\s]+@[^@\s]+", candidate) else None


def _normal_name(value: str | None) -> str | None:
    if not value:
        return None
    candidate = " ".join(value.casefold().split())
    return candidate or None


def _cell(row: dict[str, Any], key: str) -> Any:
    return row.get(key, {}).get("value")


def _cell_provenance(row: dict[str, Any], key: str) -> dict[str, Any] | None:
    return row.get(key, {}).get("provenance")


def _matches(record: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    email = _normal_email(record.get("email"))
    if email:
        email_matches = [row for row in rows if _normal_email(_cell(row, "email")) == email]
        if email_matches:
            return email_matches
    name = _normal_name(record.get("name"))
    if name:
        return [row for row in rows if _normal_name(_cell(row, "name")) == name]
    return []


def reconcile(
    *,
    attio: dict[str, Any] | None = None,
    sheet: list[dict[str, Any]] | None = None,
    gmail: list[dict[str, Any]] | None = None,
    calendar: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    availability = {"attio": attio is not None, "google_sheet": sheet is not None, "gmail": gmail is not None, "calendar": calendar is not None}
    attio_data = attio or {"pipeline": [], "potential_prospects": [], "tasks": [], "notes": [], "meetings": []}
    sheet_rows = sheet or []
    gmail_threads = gmail or []
    calendar_events = calendar or []
    result: dict[str, Any] = {
        "upcoming_meetings": [], "follow_ups": [], "untapped_prospects": [],
        "fundraising_ideas_inputs": [], "conflicts": [], "coverage": {},
    }

    for event in calendar_events:
        evidence = event["provenance"]
        result["upcoming_meetings"].append({
            "title": assertion(event.get("title"), evidence),
            "start": assertion(event.get("start"), evidence),
            "end": assertion(event.get("end"), evidence),
            "attendees": assertion(event.get("attendees", []), evidence),
        })
    for meeting in attio_data.get("meetings", []):
        evidence = provenance("attio_meeting", meeting["id"], meeting.get("updated_at") or meeting.get("start_at"))
        result["upcoming_meetings"].append({
            "title": assertion(meeting.get("title"), evidence),
            "start": assertion(meeting.get("start_at"), evidence),
            "end": assertion(meeting.get("end_at"), evidence),
            "attendees": assertion(meeting.get("attendees", []), evidence),
        })
    result["upcoming_meetings"].sort(key=lambda item: (item["start"]["value"] or "", item["title"]["value"] or ""))

    for thread in gmail_threads:
        for commitment in thread.get("commitments", []):
            evidence = commitment["provenance"]
            result["follow_ups"].append({
                "action": assertion(commitment.get("text"), evidence),
                "deadline": assertion(commitment.get("deadline"), evidence),
                "thread_id": assertion(thread["thread_id"], thread["provenance"]),
            })
    for task in attio_data.get("tasks", []):
        evidence = provenance("attio_task", task["id"], task.get("updated_at"))
        result["follow_ups"].append({
            "action": assertion(task.get("content"), evidence),
            "deadline": assertion(task.get("due_at"), evidence),
        })

    untapped = {"uncontacted", "not contacted", "untapped", "new"}
    for row in sheet_rows:
        status = str(_cell(row, "status") or "")
        if status.casefold().strip() not in untapped:
            continue
        status_evidence = _cell_provenance(row, "status") or provenance("google_sheet", "unknown-cell", confidence="low")
        name_evidence = _cell_provenance(row, "name") or status_evidence
        item = {
            "name": assertion(_cell(row, "name"), name_evidence),
            "email": assertion(_cell(row, "email"), _cell_provenance(row, "email") or name_evidence),
            "status": assertion(status, status_evidence),
            "candidate_only": assertion(False, status_evidence),
        }
        if "approach" in row:
            item["suggested_approach_input"] = assertion(_cell(row, "approach"), _cell_provenance(row, "approach") or status_evidence)
        result["untapped_prospects"].append(item)

    if sheet is None:
        for record in attio_data.get("pipeline", []):
            stage = record.get("stage", {})
            if str(stage.get("value") or "").casefold().strip() not in untapped:
                continue
            evidence = stage.get("provenance") or provenance("attio_list_entry", "unknown-entry", confidence="low")
            result["untapped_prospects"].append({
                "name": assertion(record.get("name"), evidence),
                "email": assertion(record.get("email"), evidence),
                "status": stage,
                "candidate_only": assertion(False, evidence),
            })

    if not sheet_rows:
        for candidate in attio_data.get("potential_prospects", []):
            evidence = candidate["provenance"]
            result["untapped_prospects"].append({
                "name": assertion(candidate.get("name"), evidence),
                "email": assertion(candidate.get("email"), evidence),
                "status": assertion(None, evidence),
                "candidate_only": assertion(True, evidence),
            })

    for note in attio_data.get("notes", []):
        evidence = provenance("attio_note", note["id"], note.get("created_at"), "medium")
        result["fundraising_ideas_inputs"].append({"input": assertion(note.get("content"), evidence)})

    for record in attio_data.get("pipeline", []):
        matches = _matches(record, sheet_rows)
        if len(matches) > 1:
            ids = sorted(
                source_id
                for row in matches
                if (source_id := (_cell_provenance(row, "email") or _cell_provenance(row, "name") or {}).get("source_id"))
            )
            result["conflicts"].append({
                "kind": "ambiguous_identity",
                "record": assertion(record.get("record_id"), record["stage"]["provenance"]),
                "candidate_source_ids": ids,
                "provenance": record["stage"]["provenance"],
            })
        elif len(matches) == 1:
            sheet_status = matches[0].get("status")
            attio_stage = record.get("stage")
            if sheet_status and attio_stage and str(sheet_status.get("value", "")).casefold() != str(attio_stage.get("value", "")).casefold():
                result["conflicts"].append({
                    "kind": "pipeline_status",
                    "authoritative_source": "google_sheet",
                    "identity": assertion(record.get("email") or record.get("name"), sheet_status["provenance"]),
                    "values": {"google_sheet": sheet_status, "attio": attio_stage},
                    "provenance": sheet_status["provenance"],
                })

    for source, available in availability.items():
        result["coverage"][source] = {
            "available": available,
            "provenance": provenance("collector_configuration", source, confidence="high"),
        }
    return result
