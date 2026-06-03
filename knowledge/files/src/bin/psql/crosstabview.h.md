---
path: src/bin/psql/crosstabview.h
anchor_sha: 4b0bf0788b0
loc: 29
depth: read
---

# crosstabview.h

- **Source path:** `source/src/bin/psql/crosstabview.h`
- **Lines:** 29
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `crosstabview.c` (implementation), `fe_utils/print.h` (the print engine the pivoted result is fed into).

## Purpose

Public surface for `\crosstabview` — one entry point plus one tuning constant.

## Public surface

- `CROSSTABVIEW_MAX_COLUMNS` (24) — `1600`. Caps the number of distinct horizontal-header values to avoid pathological cartesian blow-up. Comment notes the value matches the per-table column-count limit "but it could be as much as INT_MAX theoretically." [from-comment, crosstabview.h:14-24]
- `PrintResultInCrosstab(res)` (27) — pivot a `PGresult` according to `pset.ctv_args[0..3]` and print it. [verified-by-code, crosstabview.h:27]

## Phase D notes

- The 1600 limit is a DoS guard against `N x N` cartesian queries. **Caller-side defense** — the SQL has already run and the result is in memory; the limit only stops the in-memory pivot growth. So a malicious caller could still drown the client at SQL-result time. [inferred, crosstabview.h:14-24] [maybe — DoS surface]

## Confidence tag tally
`[verified-by-code]=1 [from-comment]=1 [inferred]=1`
