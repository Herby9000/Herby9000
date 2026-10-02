"""Local-only Decision Terminal command-line interface."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from email.policy import SMTP
from pathlib import Path
from typing import Any, Sequence

from .candidates import extract_candidates
from .commands import apply_commands, parse_commands
from .email_message import build_edition_message
from .inputs import normalize_business_notes, normalize_calendar, normalize_gmail
from .render import QUEUES, render_html
from .state import DecisionState


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build private Decision Terminal editions from local snapshots")
    subparsers = parser.add_subparsers(dest="operation", required=True)

    build = subparsers.add_parser("build", help="normalize sources, synchronize state, and render an edition")
    build.add_argument("--gmail", type=Path)
    build.add_argument("--calendar", type=Path)
    build.add_argument("--notes", type=Path)
    build.add_argument("--state", type=Path, required=True)
    build.add_argument("--format", choices=("json", "html", "rfc822"), default="json")
    build.add_argument("--output", type=Path)
    build.add_argument("--edition-label", default="")
    build.add_argument("--edition-id")
    build.add_argument("--sent-at")
    build.add_argument("--from", dest="sender")
    build.add_argument("--to", dest="recipient")
    build.add_argument("--message-id-domain")
    build.add_argument("--in-reply-to")
    build.add_argument("--reference", action="append", default=[])

    commands = subparsers.add_parser("commands", help="apply an authenticated local reply to state")
    commands.add_argument("--reply", type=Path, required=True)
    commands.add_argument("--sender", required=True)
    commands.add_argument("--state", type=Path, required=True)
    commands.add_argument("--output", type=Path)
    return parser


def _document(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "items": items,
        "queues": {queue: [item["id"] for item in items if item["queue"] == queue] for queue in QUEUES},
    }


def _write(content: str | bytes, output: Path | None) -> None:
    if output:
        if isinstance(content, bytes):
            output.write_bytes(content)
        else:
            output.write_text(content, encoding="utf-8")
        return
    if isinstance(content, bytes):
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is not None:
            buffer.write(content)
        else:
            sys.stdout.write(content.decode("utf-8"))
    else:
        sys.stdout.write(content)


def _build(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    sources = []
    if args.gmail:
        sources.extend(normalize_gmail(args.gmail))
    if args.calendar:
        sources.extend(normalize_calendar(args.calendar))
    if args.notes:
        sources.extend(normalize_business_notes(args.notes))
    candidates = extract_candidates(sources)
    state = DecisionState(args.state)
    state.synchronize(candidates)
    items = state.items_for_edition()

    if args.format == "json":
        content: str | bytes = json.dumps(_document(items), sort_keys=True, separators=(",", ":")) + "\n"
    else:
        html = render_html(items, edition_label=args.edition_label)
        if args.format == "html":
            content = html
        else:
            required = {
                "--edition-id": args.edition_id,
                "--sent-at": args.sent_at,
                "--from": args.sender,
                "--to": args.recipient,
                "--message-id-domain": args.message_id_domain,
            }
            missing = [option for option, value in required.items() if not value]
            if missing:
                parser.error(f"rfc822 format requires {', '.join(missing)}")
            try:
                sent_at = datetime.fromisoformat(args.sent_at.replace("Z", "+00:00"))
            except ValueError as error:
                parser.error(f"invalid --sent-at: {error}")
            message = build_edition_message(
                html,
                edition_id=args.edition_id,
                sent_at=sent_at,
                sender=args.sender,
                recipient=args.recipient,
                message_id_domain=args.message_id_domain,
                in_reply_to=args.in_reply_to,
                references=args.reference,
            )
            content = message.as_bytes(policy=SMTP)
    _write(content, args.output)
    return 0


def _commands(args: argparse.Namespace) -> int:
    commands = parse_commands(args.reply.read_text(encoding="utf-8"), args.sender)
    results = apply_commands(DecisionState(args.state), commands)
    content = json.dumps({"results": results}, sort_keys=True, separators=(",", ":")) + "\n"
    _write(content, args.output)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.operation == "build":
        return _build(args, parser)
    return _commands(args)


if __name__ == "__main__":
    raise SystemExit(main())
