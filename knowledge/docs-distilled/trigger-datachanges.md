---
source_url: https://www.postgresql.org/docs/current/trigger-datachanges.html
fetched_at: 2026-06-09T20:48:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Visibility of Data Changes (in Triggers)

What a trigger function *sees* when it queries the database (via SPI or
otherwise). The rules are a direct consequence of the MVCC snapshot +
command-counter model; mislabeled volatility silently breaks them.

## The timing/level matrix

- **Statement-level `BEFORE`:** sees **none** of the statement's changes (it
  hasn't run yet). [from-docs]
- **Statement-level `AFTER`:** sees **all** of the statement's completed
  changes. [from-docs]
- **Row-level `BEFORE`:** does **not** see the current row's change (not made
  yet), **but does** see changes already made to **earlier rows of the same
  outer command**. [from-docs]
- **Row-level `AFTER`:** sees **all** changes of the outer command (fully
  applied). [from-docs]
- **Row-level `INSTEAD OF`:** sees the effects of **prior `INSTEAD OF` firings**
  in the same command. [from-docs]

## The non-determinism caveat

Because a single command may visit affected rows **in any order**, the "earlier
rows are visible" rule for row-level `BEFORE` triggers makes cross-row
visibility **order-dependent and therefore unpredictable** — do not write a
trigger whose correctness depends on which sibling rows it can see. [from-docs]

## The volatility gotcha (easy to miss)

- These visibility rules apply **only to `VOLATILE` trigger functions** (the
  normal case). A trigger function declared **`STABLE` or `IMMUTABLE` sees
  *none* of the calling command's changes**, regardless of timing/level —
  because it rides the calling query's frozen snapshot. [from-docs]
  [cross: [[knowledge/docs-distilled/xfunc-volatility.md]]]

## When you query the firing table from inside a trigger

Combine three things before trusting what a `SELECT`/SPI call returns: (1) the
trigger's BEFORE/AFTER timing, (2) the function's volatility label, (3) the
unpredictable row-processing order. Re-querying the table the trigger fired on
is where these interact and surprise people. [from-docs]

## Links into corpus
- [[knowledge/docs-distilled/trigger-interface.md]] — the C `TriggerData` companion.
- [[knowledge/docs-distilled/xfunc-volatility.md]] — why STABLE/IMMUTABLE triggers go blind.
- [[knowledge/architecture/mvcc.md]] — the snapshot + command-counter model underneath.
- [[knowledge/files/src/backend/commands/trigger.c.md]] — trigger firing + snapshot handling.
- [[knowledge/files/src/backend/utils/adt/ri_triggers.c.md]] — RI triggers that rely on AFTER visibility.
- Skill: `fmgr-and-spi` — SPI visibility (`SPI_register_trigger_data`, snapshot push) inside triggers.

## Gaps / follow-ups
- The deep SPI-visibility mechanics (`spi-visibility`) and the command-counter
  increment points are a separate chapter / the per-file `spi.c` doc.
