"""Command-line entry point for local, read-only briefing collection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .attio import AttioCollector
from .inputs import parse_calendar, parse_gmail, parse_xlsx
from .reconcile import reconcile
from .render import render_markdown


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a shadow fundraising briefing from local inputs")
    parser.add_argument("--attio", type=Path, help="local Attio JSON fixture")
    parser.add_argument("--attio-list-id", help="authoritative Attio list ID")
    parser.add_argument("--sheet", type=Path, help="local XLSX workbook")
    parser.add_argument("--sheet-tab", action="append", default=[], help="fundraising worksheet (repeatable)")
    parser.add_argument("--gmail", type=Path, help="local compact Gmail JSON")
    parser.add_argument("--calendar", type=Path, help="local compact Calendar JSON")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="explicit output path; defaults to stdout")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.attio and not args.attio_list_id:
        parser.error("--attio-list-id is required with --attio")
    if args.sheet and not args.sheet_tab:
        parser.error("at least one --sheet-tab is required with --sheet")

    attio = None
    if args.attio:
        payload = json.loads(args.attio.read_text(encoding="utf-8"))
        attio = AttioCollector(args.attio_list_id).collect(payload)
    sheet = parse_xlsx(args.sheet, args.sheet_tab) if args.sheet else None
    gmail = parse_gmail(args.gmail) if args.gmail else None
    calendar = parse_calendar(args.calendar) if args.calendar else None
    briefing = reconcile(attio=attio, sheet=sheet, gmail=gmail, calendar=calendar)
    rendered = render_markdown(briefing) if args.format == "markdown" else json.dumps(briefing, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
