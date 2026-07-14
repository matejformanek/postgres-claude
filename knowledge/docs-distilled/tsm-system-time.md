---
source_url: https://www.postgresql.org/docs/current/tsm-system-time.html
fetched_at: 2026-07-13T20:52:00Z
anchor_sha: d92e98340fcb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.44 tsm_system_time — the SYSTEM_TIME sampling method"
maps_to_skill: tablesample-method
---

# Docs distilled — tsm_system_time (time-bounded TABLESAMPLE method)

The second pluggable-`TABLESAMPLE` reference implementation: identical skeleton
to `tsm_system_rows`, but the stop condition is a **wall-clock budget** rather
than a row count — "read as much as you can in N milliseconds." First corpus
coverage of this module; best read as a diff against tsm_system_rows.

## Non-obvious claims

- **`SYSTEM_TIME(ms)` takes a millisecond budget (a float8), not a row count.**
  `SELECT * FROM t TABLESAMPLE SYSTEM_TIME(1000)` returns as many rows as it can
  read in ~1 second, or the whole table if that finishes sooner. [from-docs]
  The handler even carries a long comment stressing the argument "is expressed
  in milliseconds" [[tsm_system_time.c:145]]. [verified-by-code @ d92e98340fcb]
- **Same `TsmRoutine` node, one fewer meaningful callback.** The handler
  `tsm_system_time_handler` [[tsm_system_time.c:82]] does the same
  `makeNode(TsmRoutine)` [[tsm_system_time.c:84]] and wires
  `NextSampleBlock = system_time_nextsampleblock` [[tsm_system_time.c:95]].
  The interesting logic lives in that block callback, which checks elapsed time
  against the budget and stops — `start_time`/`lb` state is initialized on the
  first `NextSampleBlock` call [[tsm_system_time.c:208]].
  [verified-by-code @ d92e98340fcb]
- **Block-level, hence biased, hence no `REPEATABLE`** — same three caveats as
  `tsm_system_rows`: clustering effects on small samples, and no reproducible
  seed because the sample size is nondeterministic (it depends on I/O speed).
  [from-docs]
- **Why two modules instead of one:** `SYSTEM_ROWS` bounds the *result size*;
  `SYSTEM_TIME` bounds the *query cost*. Pick `SYSTEM_TIME` when you care that a
  dashboard query never runs longer than X ms even on a table that grows.
  [from-docs]
- **Trusted extension** — non-superuser installable with `CREATE`. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/tsm-system-rows.md]] — the row-bounded sibling
  (this run); same skeleton.
- [[knowledge/docs-distilled/tablesample-method.md]] — the `TsmRoutine`
  interface both modules implement.
- [[knowledge/docs-distilled/tablesample-support-functions.md]] — support
  functions available to a sampling method.

## Confidence

Millisecond-budget semantics, block-level bias, and no-REPEATABLE are
[from-docs]. The `TsmRoutine` handler skeleton, the milliseconds comment, and
the single-callback wiring are [verified-by-code @ d92e98340fcb] against
`contrib/tsm_system_time/tsm_system_time.c`.
