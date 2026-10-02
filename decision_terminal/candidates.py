"""Create deterministic, evidence-preserving Decision Terminal candidates."""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List

_QUEUE_BY_KIND = {
    "decision": "Decide",
    "approval": "Approve",
    "delegation": "Delegate",
    "waiting": "Chase/Waiting",
    "preparation": "Prepare",
    "stale": "Stale",
    "commitment": "Chase/Waiting",
}
_REQUIRED = ("key", "kind", "summary", "why_it_matters", "proposed_next_action", "confidence")
_CONFIDENCE = {"high", "medium", "low"}


def _stable_id(candidate: Dict[str, Any]) -> str:
    provenance = candidate["provenance"]
    identity = "\x1f".join((provenance["source_type"], provenance["source_id"], str(candidate["key"])))
    return "DT-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12].upper()


def _evidenced_value(value: Any, field: str) -> Any:
    if not isinstance(value, dict) or not value.get("evidence") or value.get("value") in (None, ""):
        raise ValueError(f"{field} must contain value and evidence")
    return value["value"]


def extract_candidates(sources: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract and classify candidates; source-provided evidence is never augmented."""
    output = []
    for source in sources:
        for candidate in source.get("candidates", []):
            missing = [field for field in _REQUIRED if candidate.get(field) in (None, "")]
            if missing:
                raise ValueError(f"candidate missing required fields: {', '.join(missing)}")
            kind = str(candidate["kind"]).lower()
            if kind not in _QUEUE_BY_KIND:
                raise ValueError(f"unsupported candidate kind: {kind}")
            confidence = str(candidate["confidence"]).lower()
            if confidence not in _CONFIDENCE:
                raise ValueError(f"unsupported confidence: {confidence}")
            item = {
                "id": _stable_id(candidate),
                "queue": _QUEUE_BY_KIND[kind],
                "summary": str(candidate["summary"]),
                "why_it_matters": str(candidate["why_it_matters"]),
                "proposed_next_action": str(candidate["proposed_next_action"]),
                "confidence": confidence,
                "provenance": dict(candidate["provenance"]),
            }
            for field in ("owner", "due_date", "review_date"):
                if field in candidate:
                    item[field] = _evidenced_value(candidate[field], field)
            output.append(item)
    return sorted(output, key=lambda item: (item["queue"], item["id"]))
