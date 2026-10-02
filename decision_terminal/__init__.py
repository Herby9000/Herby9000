"""Decision Terminal: local decision queues built from trusted-upstream snapshots."""

from .candidates import extract_candidates
from .inputs import normalize_business_notes, normalize_calendar, normalize_gmail

__all__ = [
    "extract_candidates",
    "normalize_business_notes",
    "normalize_calendar",
    "normalize_gmail",
]
