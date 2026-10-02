# First Spike briefing collector

A deterministic Python 3.11, standard-library-only collector for producing a read-only fundraising shadow briefing from local synthetic fixtures or inputs prepared by a trusted upstream collector.

## Safety boundary

- The CLI has no HTTP client, authentication flow, token support, or network-write behavior.
- The Attio request policy permits `GET` and only the documented record/list-entry query forms of `POST`; all other methods and POST paths are rejected.
- The configured Attio list is the only source of Attio pipeline state. Other people/company records are marked candidate-only, and data attached only to unrelated lists is excluded.
- Gmail and Calendar adapters accept compact local JSON only.
- XLSX files are opened read-only and never modified.
- Output suggestions are evidence inputs for human review. The renderer removes operational wording that tells a reader to send email, update CRM, or contact investors.

All committed examples use reserved `.test` addresses and fictional names.

## CLI

Run from the repository root:

```text
python3.11 -m first_spike_briefing \
  --attio first_spike_briefing/fixtures/attio.json \
  --attio-list-id list-primary \
  --gmail first_spike_briefing/fixtures/gmail.json \
  --calendar first_spike_briefing/fixtures/calendar.json \
  --format json
```

For Sheets, supply `--sheet workbook.xlsx` and repeat `--sheet-tab Fundraise` for every configured fundraising tab. Use `--format markdown` for the bounded four-section shadow briefing. By default output goes to stdout; `--output PATH` is the only file-writing option.

## Input notes

Attio JSON contains `lists`, `list_attributes`, `list_entries`, `records`, `tasks`, `notes`, and `meetings`. Gmail JSON contains a `threads` array with compact message metadata. Calendar JSON contains an `events` array. These formats are transport-neutral snapshots; collection and authentication happen outside this package.

The XLSX reader supports normal shared-string, inline-string, and scalar cells. It reads cached cell values and does not calculate formulas. Each extracted cell receives workbook, tab, and cell-reference provenance.

## Output

JSON always has these sections, in the reconciliation model:

- `upcoming_meetings`
- `follow_ups`
- `untapped_prospects`
- `fundraising_ideas_inputs`
- `conflicts`
- `coverage`

Assertions contain source type, source identifier, observed timestamp when available, and confidence. Identity matching prefers exact case-insensitive email and falls back to conservatively normalized exact names. Duplicate matches and source disagreements are surfaced rather than merged. Google Sheet status remains authoritative.

## Verification

```text
python3.11 -m unittest discover -s first_spike_briefing/tests -v
python3.11 -m compileall -q first_spike_briefing
```
