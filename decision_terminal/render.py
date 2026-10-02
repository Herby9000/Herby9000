"""Compact HTML rendering for private Decision Terminal editions."""
from __future__ import annotations

from html import escape
from typing import Any, Dict, Iterable
from urllib.parse import urlparse

QUEUES = ("Decide", "Approve", "Delegate", "Chase/Waiting", "Prepare", "Stale")


def _text(value: Any) -> str:
    return escape(str(value), quote=True)


def _source(provenance: Dict[str, Any]) -> str:
    label = f"{provenance.get('source_type', 'source')} · {provenance.get('source_id', 'unknown')}"
    url = provenance.get("source_url")
    if isinstance(url, str) and urlparse(url).scheme.lower() in {"http", "https"}:
        return f'<a href="{_text(url)}">{_text(label)}</a>'
    return _text(label)


def render_html(items: Iterable[Dict[str, Any]], edition_label: str = "") -> str:
    """Render all six queues as a small-screen, email-safe HTML document."""
    grouped = {queue: [] for queue in QUEUES}
    for item in items:
        queue = item.get("queue")
        if queue not in grouped:
            raise ValueError(f"unsupported queue: {queue}")
        grouped[queue].append(item)

    sections = []
    for queue in QUEUES:
        cards = []
        for item in sorted(grouped[queue], key=lambda value: value["id"]):
            confidence = str(item.get("confidence", "low")).lower()
            uncertainty = "High confidence" if confidence == "high" else f"Uncertain · {confidence} confidence"
            optional = []
            if item.get("owner"):
                optional.append(f"<div><b>Owner:</b> {_text(item['owner'])}</div>")
            if item.get("due_date"):
                optional.append(f"<div><b>Due:</b> {_text(item['due_date'])}</div>")
            if item.get("review_date"):
                optional.append(f"<div><b>Review:</b> {_text(item['review_date'])}</div>")
            cards.append(
                '<article class="card">'
                f'<div class="item-id">{_text(item["id"])}</div>'
                f'<h3>{_text(item["summary"])}</h3>'
                f'<p>{_text(item["why_it_matters"])}</p>'
                f'<p><b>Next:</b> {_text(item["proposed_next_action"])}</p>'
                + "".join(optional)
                + f'<div class="meta">{_text(uncertainty)} · Source: {_source(item["provenance"])}</div>'
                + "</article>"
            )
        if not cards:
            cards.append('<p class="empty">No current items.</p>')
        sections.append(f'<section><h2>{_text(queue)}</h2>{"".join(cards)}</section>')

    label = f'<p class="edition">{_text(edition_label)}</p>' if edition_label else ""
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<style>body{margin:0;background:#f4f5f2;color:#20231f;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}'
        '.wrap{max-width:600px;margin:0 auto;padding:16px}.edition,.meta,.item-id{color:#62675f;font-size:12px}'
        'h1{font-size:26px;margin:4px 0}h2{font-size:19px;margin:24px 0 8px}h3{font-size:17px;margin:6px 0}'
        '.card{background:#fff;border:1px solid #dfe2dc;border-radius:12px;margin:8px 0;padding:14px}'
        '.card p{font-size:15px;line-height:1.4;margin:8px 0}.meta{border-top:1px solid #eceee9;margin-top:12px;padding-top:8px;overflow-wrap:anywhere}'
        'a{color:#245c3a}.empty{color:#777;font-size:14px}@media(max-width:480px){.wrap{padding:10px}.card{padding:12px}}</style>'
        f'</head><body><main class="wrap"><h1>Decision Terminal</h1>{label}{"".join(sections)}</main></body></html>'
    )
