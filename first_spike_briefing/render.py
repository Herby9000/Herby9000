"""Bounded Markdown rendering for human-reviewed shadow briefings."""
from __future__ import annotations

import re
from typing import Any

_FORBIDDEN = re.compile(r"\b(?:send\s+(?:an?\s+)?email|update\s+(?:the\s+)?crm|contact\s+investors?)\b", re.IGNORECASE)


def _safe(value: Any, limit: int = 240) -> str:
    text = " ".join(str(value).split()) if value is not None else ""
    text = _FORBIDDEN.sub("[action wording omitted]", text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _uncertain(*assertions: dict[str, Any]) -> str:
    confidence = [item.get("provenance", {}).get("confidence") for item in assertions]
    if any(value and value != "high" for value in confidence):
        return " [uncertain: low confidence]"
    return ""


def _bounded(lines: list[str], count: int, maximum: int) -> list[str]:
    if count <= 0:
        return lines
    visible = lines[:maximum]
    omitted = count - len(visible)
    if omitted:
        visible.append(f"- {omitted} additional item{'s' if omitted != 1 else ''} omitted by output bound.")
    return visible


def render_markdown(briefing: dict[str, Any], max_items_per_section: int = 20) -> str:
    if max_items_per_section < 1 or max_items_per_section > 100:
        raise ValueError("max_items_per_section must be between 1 and 100")
    sections: list[tuple[str, list[str]]] = []

    meetings = briefing.get("upcoming_meetings", [])
    meeting_lines = []
    for item in meetings:
        title = _safe(item["title"].get("value")) or "Untitled meeting"
        start = _safe(item.get("start", {}).get("value")) or "time missing"
        meeting_lines.append(f"- {title} — {start}{_uncertain(item['title'], item.get('start', {}))}")
    if not meeting_lines:
        meeting_lines = ["- Missing data: no Calendar evidence supplied."]
    sections.append(("Today's meetings", _bounded(meeting_lines, len(meetings), max_items_per_section)))

    followups = briefing.get("follow_ups", [])
    followup_lines = []
    for item in followups:
        action = _safe(item["action"].get("value")) or "action missing"
        deadline = _safe(item.get("deadline", {}).get("value")) or "deadline not evidenced"
        followup_lines.append(f"- {action} — {deadline}{_uncertain(item['action'], item.get('deadline', {}))}")
    if not followup_lines:
        followup_lines = ["- Missing data: no Gmail or Attio evidence supplied."]
    sections.append(("Follow-ups", _bounded(followup_lines, len(followups), max_items_per_section)))

    prospects = briefing.get("untapped_prospects", [])
    prospect_lines = []
    for item in prospects:
        name = _safe(item["name"].get("value")) or "name missing"
        status = _safe(item.get("status", {}).get("value")) or "status missing"
        candidate = bool(item.get("candidate_only", {}).get("value"))
        approach = _safe(item.get("suggested_approach_input", {}).get("value"))
        detail = f"candidate only; {status}" if candidate else status
        if approach:
            detail += f"; approach evidence: {approach}"
        else:
            detail += "; suggested approach missing"
        prospect_lines.append(f"- {name} — {detail}{_uncertain(item['name'], item.get('status', {}))}")
    if not prospect_lines:
        prospect_lines = ["- Missing data: no Google Sheet or Attio candidate evidence supplied."]
    sections.append(("Uncontacted prospects and suggested approach inputs", _bounded(prospect_lines, len(prospects), max_items_per_section)))

    ideas = briefing.get("fundraising_ideas_inputs", [])
    idea_lines = [f"- {_safe(item['input'].get('value')) or 'input missing'}{_uncertain(item['input'])}" for item in ideas]
    if not idea_lines:
        idea_lines = ["- Missing data: no supporting evidence supplied."]
    sections.append(("New fundraising idea inputs", _bounded(idea_lines, len(ideas), max_items_per_section)))

    blocks = ["# First Spike Shadow Briefing"]
    for heading, lines in sections:
        blocks.extend(("", f"## {heading}", *lines))
    return "\n".join(blocks) + "\n"
