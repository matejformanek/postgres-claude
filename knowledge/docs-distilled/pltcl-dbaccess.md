---
source_url: https://www.postgresql.org/docs/current/pltcl-dbaccess.html
fetched_at: 2026-07-07T20:56:00Z
anchor_sha: 9d1188f29865
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/Tcl database access (§44.5) — spi_exec / spi_prepare / spi_execp

The Tcl SPI command surface and its per-command internals (variable binding,
plan lifetime, NULL semantics). C entry points confirmed via the
`Tcl_CreateObjCommand` wiring in `pltcl_init_interp` (`source/src/pl/tcl/pltcl.c`).

## Non-obvious claims

- **`spi_exec ?-count n? ?-array name? command ?loop-body?`** → C
  `pltcl_SPI_execute` (registered `pltcl.c:529`). Returns the number of rows processed
  (0 for utility statements). By default it binds each result column into a
  **Tcl variable named after the column**; with `-array name` it binds into an
  associative array with column names as indices and the current row number in
  `name(.tupno)`. `-count n` stops after n rows (`n=0` = all). A `loop-body`
  runs once per row with `break`/`continue` honored. **NULL columns unset the
  target variable** rather than setting an empty string — the disambiguation for
  Tcl's no-NULL model. [from-docs][verified-by-code @9d1188f29865]
- **`spi_prepare query typelist`** → C `pltcl_SPI_prepare` (registered `pltcl.c:531`).
  Placeholders `$1..$n`; `typelist` is a Tcl list of type names (empty if none).
  Returns a query-ID (plan handle). **Plans persist for the whole session**, so
  you must stash the ID in a global (typically the `GD` array) to reuse it across
  calls — otherwise it re-plans. In the query string use `\$n` so Tcl doesn't
  substitute the placeholder before it reaches the planner. [from-docs][verified-by-code @9d1188f29865]
- **`spi_execp ?-count n? ?-array name? ?-nulls string? queryid ?value-list? ?loop-body?`**
  → C `pltcl_SPI_execute_plan` (registered `pltcl.c:533`). Executes a prepared plan;
  `value-list` supplies the parameter values. **`-nulls` is a string of spaces
  and `n` chars, same length as the value list**, marking which params are NULL.
  Because params are never re-parsed as SQL, `spi_execp` is injection-safe (no
  quoting needed) — the reason to prefer it over string-built `spi_exec`.
  [from-docs][verified-by-code @9d1188f29865]
- **`quote string`** doubles single-quotes and backslashes for safe interpolation
  into a `spi_exec`/`spi_prepare` string. [from-docs]
- **`subtransaction { body }`** → C `pltcl_subtransaction` (registered `pltcl.c:535`) runs
  the body in an internal subtransaction; a Tcl error rolls the subxact back
  before propagating. Same `BeginInternalSubTransaction` primitive as PL/Python
  (`pltcl.c:2366/:2376/:2393`). [from-docs][verified-by-code @9d1188f29865]
- **`elog level msg`** with `DEBUG/LOG/INFO/NOTICE/WARNING/ERROR/FATAL`: `ERROR`
  aborts the current (sub)transaction and propagates; `FATAL` aborts and closes
  the session. Routing follows `log_min_messages` / `client_min_messages`.
  [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/pltcl-overview.md]] — where these commands are
  installed into the safe interpreter.
- [[knowledge/docs-distilled/pltcl-global.md]] — the `GD` array where plan IDs
  are stashed.
- [[knowledge/docs-distilled/plperl-builtins.md]] / [[knowledge/docs-distilled/plpython-database.md]]
  — the same SPI surface in Perl / Python (materialize-vs-cursor parity).
- [[knowledge/docs-distilled/spi.md]] — the underlying C SPI API.
