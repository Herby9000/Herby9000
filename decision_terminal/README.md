# Decision Terminal

Decision Terminal is a separate, standard-library-only Python package that turns trusted-upstream, read-only JSON snapshots into a private six-queue decision edition. It has its own adapters, candidate schema, state, HTML renderer, RFC email constructor, CLI, fixtures, and tests. It does not import or analyze the First Spike briefing pipeline.

## Safety boundary

- Inputs are local JSON snapshots representing Gmail threads, Calendar events, and explicitly allowlisted business-note excerpts. The package has no API clients, authentication flows, network access, or message transport.
- All committed fixtures are synthetic and use fictional names and reserved `.test` domains.
- RFC 5322 messages are constructed only. They are written to stdout or an explicit path and are never transmitted.
- Reply commands mutate only the supplied Decision Terminal state file. The sender must normalize exactly to `chtmorris@icloud.com`.
- Items remain in state when absent from a later snapshot. Absence never implies completion.
- Business notes tagged `first_spike_private_action` are accepted only when their candidate kind is an explicit private `decision` or `commitment`.

## Input schema

Each source uses a transport-neutral envelope:

- Gmail: `{"threads": [{"id", "subject", "web_url?", "messages": [{"id", "timestamp?", "candidate?"}]}]}`
- Calendar: `{"events": [{"id", "title", "start?", "updated?", "html_link?", "candidate?"}]}`
- Business notes: `{"notes": [{"id", "allowlisted", "excerpt", "source_url?", "updated?", "tags?", "candidate?"}]}`

A candidate requires non-blank `key`, `kind`, `summary`, `why_it_matters`, `proposed_next_action`, and `confidence`. Supported kinds map to queues as follows: `decision` → Decide, `approval` → Approve, `delegation` → Delegate, `waiting` or `commitment` → Chase/Waiting, `preparation` → Prepare, and `stale` → Stale. Confidence is `high`, `medium`, or `low`.

`owner`, `due_date`, and `review_date` are optional and must each be an object containing both `value` and non-empty `evidence`; otherwise extraction rejects the candidate. Provenance is generated from the source envelope and stable source identifiers. Item IDs derive only from source type, source identifier, and candidate key, so wording changes do not change identity.

## State and replies

State begins at `candidate` and enforces the progression through `confirmed` and `active`. Active items may become `waiting`, `delegated`, `snoozed`, `completed`, or `cancelled`; non-terminal paused items may return to active. History and command metadata stay in the private JSON state file.

Authenticated reply bodies accept one command per line:

- `done DT-…`
- `snooze DT-… until YYYY-MM-DD`
- `delegate DT-… to NAME`
- `waiting DT-…` or `waiting DT-… for REASON`
- `not actionable DT-…`
- `details DT-…`
- `correct DT-… FIELD=VALUE`

State-changing commands advance a new candidate through confirmed and active before applying the requested status. Snooze values must be real ISO calendar dates. `details` records no external action; the CLI reports a local details request. Corrections are local overlays in later editions.

## CLI

Build JSON from all three bundled synthetic snapshots:

```text
python3 -m decision_terminal build \
  --gmail decision_terminal/fixtures/gmail.json \
  --calendar decision_terminal/fixtures/calendar.json \
  --notes decision_terminal/fixtures/business_notes.json \
  --state decision_terminal/state.local.json \
  --format json
```

The build format can be `json`, `html`, or `rfc822`. RFC output additionally requires an edition ID, timezone-aware sent-at value, sender, recipient, and Message-ID domain. Later editions can supply `--in-reply-to` and repeat `--reference`; the subject stays `Decision Terminal`, while each edition ID yields a unique deterministic Message-ID.

Apply a local reply file with the `commands` subcommand and explicit `--reply`, `--sender`, and `--state` paths. Output defaults to stdout; `--output` is the only edition/result output write.

## Verification

```text
python3 -m unittest discover -v
python3 -m compileall -q decision_terminal first_spike_briefing
```
