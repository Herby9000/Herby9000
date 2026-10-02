"""RFC 5322 construction for editions; this module has no transport support."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime
from typing import Iterable, Optional

_SUBJECT = "Decision Terminal"
_DOMAIN = re.compile(r"^[A-Za-z0-9.-]+$")


def build_edition_message(
    html: str,
    *,
    edition_id: str,
    sent_at: datetime,
    sender: str,
    recipient: str,
    message_id_domain: str,
    in_reply_to: Optional[str] = None,
    references: Optional[Iterable[str]] = None,
) -> EmailMessage:
    """Construct, but never transmit, a deterministic threaded email edition."""
    if not edition_id or any(character in edition_id for character in "\r\n"):
        raise ValueError("edition_id must be non-empty and single-line")
    if sent_at.tzinfo is None:
        raise ValueError("sent_at must be timezone-aware")
    if not _DOMAIN.fullmatch(message_id_domain):
        raise ValueError("invalid Message-ID domain")

    digest = hashlib.sha256(("decision-terminal\x1f" + edition_id).encode("utf-8")).hexdigest()[:24]
    message_id = f"<decision-terminal-{digest}@{message_id_domain.lower()}>"
    message = EmailMessage(policy=SMTP)
    message["Subject"] = _SUBJECT
    message["From"] = sender
    message["To"] = recipient
    message["Date"] = format_datetime(sent_at)
    message["Message-ID"] = message_id
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    reference_values = list(references or [])
    if reference_values:
        message["References"] = " ".join(reference_values)
    message.set_content("Decision Terminal edition. View the HTML alternative for the full private briefing.")
    message.add_alternative(html, subtype="html")
    message.set_boundary("decision-terminal-" + digest)
    return message
