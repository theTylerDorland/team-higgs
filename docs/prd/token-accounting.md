# PRD — Token accounting by type (schema v2.1)

**Status:** proposed · **Owner:** EM (Higgs) · **Author tier:** plan
**Upstream authority:** `.claude/agents/em.md`.

---

## 1. Purpose

The EM must be able to project the **real** API-billed cost of the platform's
work from the `runs` ledger, so Tyler can decide when (and whether) to move
off the subscription. Today `runs.token_cost` is a single lump figure — in
practice ≈ **output tokens only** — which is misleading: measured from actual
agent transcripts, cost is **cache-dominated** (a single build run priced at
**$34.26** on Opus 4.8 — ~$18 cache-read + ~$12 cache-write vs. ~$4 output).
The lump figure captures none of that. This PRD records token usage **by
type** so cost projection is accurate.

The data is already available: every dispatched agent's transcript logs
per-call `usage` with `input_tokens`, `output_tokens`,
`cache_read_input_tokens`, `cache_creation_input_tokens`. We aggregate it and
store the split.

## 2. Scope

**In:** additive migration adding four typed token columns to `runs`; `emctl`
`run finish` + a new `run update` accepting them; a standalone transcript
aggregator; tests; `db/schema.sql` + `docs/stack-backend.md` updates.

**Out (EM does post-merge, not the implementer):** updating the
`hypothetical_api_cost` metric to price from the typed columns; best-effort
backfill of existing runs from live transcripts (they live in ephemeral job
scratch, so this is time-limited and approximate — resumed agents blur run
boundaries).

## 3. Schema change (migration `0004`, additive + reversible)

Add to `runs` (all nullable `BIGINT`, default NULL — existing rows and runs
without a transcript stay NULL):
```
input_tokens        BIGINT   -- uncached input
output_tokens       BIGINT
cache_read_tokens   BIGINT   -- cache_read_input_tokens
cache_write_tokens  BIGINT   -- cache_creation_input_tokens
```
`token_cost` is left as-is (legacy lump/rough-total; the typed columns
supersede it for cost). `downgrade()` drops the four columns.

## 4. emctl surface

Follows the established `commands/ → repo/ → db` pattern, parameterized SQL,
global `--json`, same exit-code contract.

| Command | Change |
|---|---|
| `run finish` | **+** `--input-tokens --output-tokens --cache-read --cache-write` (all optional `INTEGER`, populate the new columns). Existing `--tokens`/`--cost`/`--outcome`/`--log-ref` unchanged. |
| `run update <RUN_ID>` | **new** — amend an existing (already-finished) run: same token flags plus `--tokens --cost --outcome --log-ref`. Enables correction and historical backfill. Positional `RUN_ID`. |

## 5. Transcript aggregator (standalone — keeps emctl format-agnostic)

Ship `tools/agent_token_split.py <transcript.jsonl>`:
- Reads a Claude Code agent transcript (JSONL, one message object per line;
  the API `usage` is at `message.usage`).
- Sums `input_tokens`, `output_tokens`, `cache_read_input_tokens`,
  `cache_creation_input_tokens` across all lines that carry a `usage`.
- **Tolerant:** skips unparseable/`usage`-less lines without failing; never
  raises on a malformed transcript.
- **Pure read, no side effects:** opens one file read-only, prints the four
  sums (and the resolved `model` if present) as `--json`-style output; writes
  nothing, executes nothing.
- Kept **out of `emctl`** deliberately: emctl stays generic (accepts the four
  numbers via flags); the Claude-Code-specific parsing is isolated here, so a
  transcript-format change touches one file, not the state CLI.

Usage pattern (EM): `python tools/agent_token_split.py <path>` → pipe the
four numbers into `emctl run finish/update`.

## 6. Metric (EM registers post-merge; listed as the deliverable it enables)

The EM updates `hypothetical_api_cost` to price exactly from the typed
columns, per model (per-MTok rates; cache-read = 0.1× input, cache-write =
1.25× input):

| model | input | output | cache-read | cache-write |
|---|---|---|---|---|
| claude-opus-4-8 | 5.00 | 25.00 | 0.50 | 6.25 |
| claude-sonnet-5 | 3.00 | 15.00 | 0.30 | 3.75 |
| claude-haiku-4-5 | 1.00 | 5.00 | 0.10 | 1.25 |

`cost = Σ(input×in + output×out + cache_read×cr + cache_write×cw) / 1e6`,
grouped by model. Runs into the existing `metric report` READ ONLY boundary
unchanged.

## 7. Definition of done

- `ruff` + `mypy` clean; full `pytest` green on a scratch DB; `0004`
  downgrade→upgrade round-trips.
- `run finish` and `run update` accept and persist the four token types
  (happy + unhappy: unknown run id → NotFound; bad value → Validation).
- `tools/agent_token_split.py` aggregates a small fixture transcript to the
  expected four sums, and returns cleanly on a fixture containing a malformed
  line and a `usage`-less line.
- `db/schema.sql` + `docs/stack-backend.md` updated.

## 8. Dispatch metadata

- **Role:** implementer-backend · **Tier:** execute · **prd_ref:**
  `docs/prd/token-accounting.md` · **branch:** `feat/token-accounting`.
- **Reviewers:** security (new SQL surface + a file-reading helper); cross-model.
- Environment: scratch DB on the running Postgres; do **not** touch the live
  `platform` DB.
