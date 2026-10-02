"""Local-only XLSX, Gmail JSON, and Calendar JSON input adapters."""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .attio import provenance

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _json_input(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _column_number(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        raise ValueError(f"invalid cell reference: {reference}")
    number = 0
    for character in letters.group(0):
        number = number * 26 + ord(character) - 64
    return number - 1


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def parse_xlsx(source: bytes | str | Path, tabs: list[str], source_id: str | None = None) -> list[dict[str, Any]]:
    """Read configured tabs from an XLSX ZIP without modifying the source."""
    if isinstance(source, bytes):
        workbook_bytes = source
        identity = source_id or "workbook-bytes"
    else:
        path = Path(source)
        workbook_bytes = path.read_bytes()
        identity = source_id or path.name
    requested = set(tabs)
    output: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.itertext()) for node in root.findall(f"{_MAIN}si")]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships.findall(f"{_PKG_REL}Relationship")}
        found: set[str] = set()
        for sheet in workbook.findall(f"{_MAIN}sheets/{_MAIN}sheet"):
            tab = sheet.attrib["name"]
            if tab not in requested:
                continue
            found.add(tab)
            target = targets[sheet.attrib[f"{_REL}id"]]
            target_path = target.lstrip("/") if target.startswith("/xl/") else f"xl/{target.lstrip('/')}"
            root = ET.fromstring(archive.read(target_path))
            rows: list[dict[int, tuple[str, str]]] = []
            for row in root.findall(f".//{_MAIN}row"):
                values: dict[int, tuple[str, str]] = {}
                for cell in row.findall(f"{_MAIN}c"):
                    reference = cell.attrib["r"]
                    value_node = cell.find(f"{_MAIN}v")
                    inline = cell.find(f"{_MAIN}is/{_MAIN}t")
                    raw = value_node.text if value_node is not None and value_node.text is not None else ((inline.text or "") if inline is not None else "")
                    value = shared[int(raw)] if cell.attrib.get("t") == "s" and raw else raw
                    values[_column_number(reference)] = (value, reference)
                rows.append(values)
            if not rows:
                continue
            headers = {column: _key(value) for column, (value, _) in rows[0].items() if value}
            for row in rows[1:]:
                record: dict[str, Any] = {}
                for column, header in headers.items():
                    if column not in row:
                        continue
                    value, reference = row[column]
                    record[header] = {
                        "value": value,
                        "provenance": provenance("google_sheet", f"{identity}#{tab}!{reference}"),
                    }
                if record:
                    output.append(record)
        missing = requested - found
        if missing:
            raise ValueError(f"configured worksheet(s) missing: {', '.join(sorted(missing))}")
    return output


def parse_gmail(source: str | Path | dict[str, Any]) -> list[dict[str, Any]]:
    payload = _json_input(source)
    output = []
    for thread in payload.get("threads", []):
        commitments = []
        for message in thread.get("messages", []):
            text = message.get("snippet", "")
            if re.search(r"\b(?:I|we) will\b", text, re.IGNORECASE):
                commitments.append({
                    "text": text,
                    "deadline": None,
                    "provenance": provenance("gmail_message", message["id"], message.get("timestamp"), "medium"),
                })
        output.append({
            "thread_id": thread["id"],
            "subject": thread.get("subject"),
            "participants": sorted(thread.get("participants", [])),
            "commitments": commitments,
            "provenance": provenance("gmail_thread", thread["id"], _last_timestamp(thread.get("messages", []))),
        })
    return output


def _last_timestamp(messages: list[dict[str, Any]]) -> str | None:
    values: list[str] = [timestamp for message in messages if isinstance((timestamp := message.get("timestamp")), str) and timestamp]
    return max(values) if values else None


def parse_calendar(source: str | Path | dict[str, Any]) -> list[dict[str, Any]]:
    payload = _json_input(source)
    return [{
        "event_id": event["id"],
        "title": event.get("title"),
        "start": event.get("start"),
        "end": event.get("end"),
        "attendees": sorted(event.get("attendees", [])),
        "provenance": provenance("calendar_event", event["id"], event.get("updated") or event.get("start")),
    } for event in payload.get("events", [])]
