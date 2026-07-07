---
source_url: https://www.postgresql.org/docs/current/plpython-database.html
fetched_at: 2026-07-07T20:53:00Z
anchor_sha: 9d1188f29865
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/Python database access (§46.5) — plpy.* SPI wrappers

The Python-side SPI surface: immediate execute, prepared plans, streaming
cursors, the SPIError hierarchy, and transaction control. Twin of
`plperl-builtins.md` / `pltcl-dbaccess.md`.

## Non-obvious claims

- **`plpy.execute(query [, limit])` materializes the whole result** into an
  object that emulates a list of dict/index-addressable rows
  (`rv[i]["col"]` or `rv[i][j]`, `len(rv)` = row count). The result object also
  exposes `nrows()` (rows *processed* — e.g. an UPDATE's count, not rows
  returned), `status()` (the raw `SPI_execute()` return code), `colnames()`,
  `coltypes()` (type OIDs), `coltypmods()`. Small results only. [from-docs]
- **`plpy.prepare(query [, argtypes])` → plan object; plans are cached across
  calls but you must keep the handle.** Execute via `plpy.execute(plan, [args],
  limit)` or `plan.execute([args], limit)`. Persist the handle in the **`SD`**
  (per-function) or **`GD`** (per-session, cross-function) dictionaries to reuse
  a plan across invocations — the canonical trigger idiom stores it in `SD`.
  [from-docs]
- **`plpy.cursor(query)` / `plpy.cursor(plan, [args])` streams** — no `limit`
  arg. `cursor.fetch(batch_size)` returns a result object of at most
  `batch_size` rows (empty when exhausted); iterating the cursor yields rows as
  **dicts** one at a time. `cursor.close()` frees it; unusable afterward. These
  are **not** PEP-249 DB-API cursors — name only. [from-docs]
- **Errors are `plpy.SPIError`, subclassed by SQLSTATE condition name.**
  `plpy.spiexceptions.DivisionByZero`, `.UniqueViolation`, etc. map from
  `errcodes-appendix` condition names (CamelCased). The base `plpy.SPIError`
  carries `.sqlstate`. You catch the specific subclass to branch on error class.
  [from-docs]
- **Transaction control: `plpy.commit()` / `plpy.rollback()`** (top level of a
  procedure / non-atomic context), and **`plpy.subtransaction()`** for atomic
  inner blocks (see `plpython-subtransaction.md`). [from-docs]
- **Logging wrappers** `plpy.debug/log/info/notice/warning/error/fatal` map to
  `elog` levels; `error`/`fatal` raise. `plpy.quote_literal` /
  `quote_nullable` / `quote_ident` mirror the SQL quoting builtins. [from-docs]

## The in-memory vs streaming split (mirror of the other PLs)

| | in-memory | streaming |
|---|---|---|
| call | `plpy.execute()` | `plpy.cursor()` |
| result | full set materialized | chunked on demand |
| row shape | list-of-dict result object | dicts, row-by-row |

Same "materialize vs cursor" contract as PL/Perl (`spi_exec_query` vs
`spi_query`) and PL/Tcl (`spi_exec` full vs `-count`).

## Links into corpus

- [[knowledge/docs-distilled/plpython-subtransaction.md]] — explicit subxact for
  SPIError recovery.
- [[knowledge/docs-distilled/spi.md]] / [[knowledge/docs-distilled/spi-memory.md]]
  — the C SPI layer under `plpy.execute`/`plpy.cursor`.
- [[knowledge/docs-distilled/errcodes-appendix.md]] — the SQLSTATE condition
  names that become `spiexceptions.*`.
