---
source_url: https://www.postgresql.org/docs/current/tsm-system-rows.html
fetched_at: 2026-07-13T20:51:00Z
anchor_sha: d92e98340fcb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.43 tsm_system_rows — the SYSTEM_ROWS sampling method"
maps_to_skill: tablesample-method
---

# Docs distilled — tsm_system_rows (row-limited TABLESAMPLE method)

A complete, minimal implementation of the pluggable `TABLESAMPLE` interface:
one C function returning a `TsmRoutine` node. The reference to read alongside
`tablesample-method` when you want "give me approximately N rows, cheaply."
First corpus coverage of this module.

## Non-obvious claims

- **`SYSTEM_ROWS(n)` returns *exactly* n rows** — unless the table has fewer
  than n visible rows, in which case the whole table comes back.
  `SELECT * FROM t TABLESAMPLE SYSTEM_ROWS(100)`. [from-docs]
- **It's block-level, so it's biased.** Like the built-in `SYSTEM` method it
  reads whole blocks, not individually-chosen rows; the docs warn the result
  "may be subject to clustering effects, especially if only a small number of
  rows are requested." Not a substitute for a true random sample. [from-docs]
- **No `REPEATABLE` support.** Because it stops as soon as it has enough rows,
  it can't offer a reproducible seed. [from-docs]
- **The whole extension is one handler function returning a `TsmRoutine`.**
  `tsm_system_rows_handler(PG_FUNCTION_ARGS)` [[tsm_system_rows.c:81]] does
  `TsmRoutine *tsm = makeNode(TsmRoutine)` [[tsm_system_rows.c:83]] and fills the
  three callbacks that matter: `SampleScanGetSampleSize`
  [[tsm_system_rows.c:91]] (cost/row estimate), `NextSampleBlock`
  [[tsm_system_rows.c:94]] (which block to read next), and `NextSampleTuple`
  [[tsm_system_rows.c:95]] (which tuples in that block to emit). This is the
  minimal shape of any custom sampling method. [verified-by-code @ d92e98340fcb]
- **`NextSampleBlock` drives its own pseudo-random block walk**; the "lb"
  (last-block) state is initialized lazily on the first `NextSampleBlock` call
  [[tsm_system_rows.c:191]], and the scan halts once the row target is met —
  which is exactly why `REPEATABLE` isn't offered. [verified-by-code @ d92e98340fcb]
- **Trusted extension** — non-superuser installable with `CREATE`. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/tablesample-method.md]] — the `TsmRoutine`
  interface definition this module implements.
- [[knowledge/docs-distilled/tablesample-support-functions.md]] — the support
  functions a sampling method may supply.
- [[knowledge/docs-distilled/tsm-system-time.md]] — the time-bounded sibling
  (this run); same skeleton, different stop condition.

## Confidence

Row-exactness, block-level bias, and the no-REPEATABLE limitation are
[from-docs]. The `TsmRoutine` skeleton and the three callback assignments are
[verified-by-code @ d92e98340fcb] against
`contrib/tsm_system_rows/tsm_system_rows.c`.
