# `contrib/spi/refint.c`

> **⚠️ REMOVED UPSTREAM.** This file no longer exists in PostgreSQL
> master. It was deleted by commit `5e90e0914cfa` ("Remove the refint
> extension.") together with the rest of the `contrib/spi` tutorial
> trigger examples for the referential-integrity demo. Verified 404 at
> anchor `c1702cb51363` via
> `raw.githubusercontent.com/postgres/postgres/c1702cb51363/contrib/spi/refint.c`
> (2026-07-11, pg-quality-auditor anchor-bump audit). The notes below are
> retained as **historical reference** for the SPI-in-trigger pattern the
> file once demonstrated; every `source/contrib/spi/refint.c:<line>` cite
> below is dead and must not be treated as live.

- **Last verified commit:** `e18b0cb7344` (file removed by `5e90e0914cfa`; historical)
- **Lines:** 538 (at removal)
- **Source:** `source/contrib/spi/refint.c` — **removed upstream**

Tutorial-example trigger functions that implement referential integrity
("RI") **using only SPI** instead of relying on the executor's built-in
FOREIGN KEY infrastructure. Two functions: `check_primary_key` (call on
the child table's INSERT/UPDATE to verify the parent row exists) and
`check_foreign_key` (call on the parent table's DELETE/UPDATE to verify
no children point to the key, with action `restrict|setnull|cascade`).
This is the **canonical PG demo** of how to call `SPI_connect`,
`SPI_prepare`, `SPI_execp`, and `SPI_finish` in real trigger code.
[verified-by-code]

## API / entry points

- `check_primary_key(PG_FUNCTION_ARGS)` `:34-189` — AFTER-ROW
  INSERT/UPDATE trigger. Trigger args:
  `(Fkey1, Fkey2, …, Ptable, Pkey1, Pkey2, …)` — odd-numbered:
  the child's key columns, then the parent table name, then the
  parent's key columns. SELECTs `SELECT 1 FROM ptable WHERE
  pkey1=$1 AND pkey2=$2 …` LIMIT 1; if 0 rows → ereport(ERROR
  triggered_action_exception). [verified-by-code]
- `check_foreign_key(PG_FUNCTION_ARGS)` `:205-538` — AFTER-ROW
  DELETE/UPDATE trigger on parent. Trigger args:
  `(nrefs, action, Pkey1, Pkey2, …, Ftable1, Fkey11, Fkey12, …,
  Ftable2, Fkey21, …)`. For each child table, depending on action
  letter:
  - `'r'estrict` → `SELECT 1 FROM ftable WHERE fk=$1 ...` LIMIT 1;
    error if any row.
  - `'c'ascade` on DELETE → `DELETE FROM ftable WHERE ...`.
  - `'c'ascade` on UPDATE → `UPDATE ftable SET fk=newkey ... WHERE ...`.
  - `'s'etnull` → `UPDATE ftable SET fk1=null, fk2=null ... WHERE ...`.
  [verified-by-code]

## The pattern (what this file teaches)

1. **`SPI_connect()` opens the SPI session**, `SPI_finish()` closes
   it. Every `return` path MUST call `SPI_finish` — the early-return
   on NULL key value handles this manually at `:137-138, 335-337`. [verified-by-code]
2. **`SPI_prepare(sql, nargs, argtypes)`** creates a `SPIPlanPtr`
   without binding parameters. The plan lives in the SPI memory
   context which is freed by `SPI_finish`. [verified-by-code]
3. **`SPI_execp(plan, Datum_args, NULL_nulls_string, tcount)`** —
   passing NULL for the nulls string means "no Datums are null"
   (we already pre-checked at `:135-139`). `tcount=1` for the
   restrict case limits the scan, otherwise `tcount=0` = all. [verified-by-code]
4. **`SPI_processed`** is a global that holds row count from the
   most recent SPI call. [verified-by-code] `:180, 512`
5. **`SPI_result_code_string(rc)`** turns SPI_ERROR_* into a
   debuggable string for `elog(ERROR, ...)`. [verified-by-code]
   `:163, 352`
6. **`SPI_getvalue(tuple, tupdesc, fnum)`** returns the column as a
   C string (uses the type's output function). Used to compare key
   values before/after an UPDATE in textual form — comment
   acknowledges "For the moment we use string presentation of
   values..." (`:341-343`) i.e. this is fragile and could be wrong
   for types where text representation isn't 1-1. [from-comment]

## Notable invariants / details

- **INV-1: NULL key columns mean "no constraint"**. If any FK
  column is NULL, both functions silently return the tuple without
  doing anything. Standard SQL FK behaviour. `:135-139, 333-337`
  [verified-by-code]
- **INV-2: UPDATE with unchanged key skips work** (`check_foreign_key`
  `:480-485`). Comparison is `strcmp(oldval, newval)` on
  `SPI_getvalue` strings, which can be wrong for: NUMERIC with
  trailing-zero changes, JSONB representation differences, anything
  whose textual form isn't canonical. [from-comment +
  verified-by-code]
  **[ISSUE-correctness: text-based key-change detection can fail
  for types with non-canonical out-text (likely)]**
- **INV-3: Cascade-UPDATE generates SQL by string substitution.**
  `:415-427` interpolates new column values via `quote_literal_cstr`
  if non-NULL or literal `NULL`. NOT parameterised because new
  values are part of the SET clause not the WHERE; only WHERE is
  bound. So a NUMERIC, BYTEA, TIMESTAMPTZ etc. has to round-trip
  through `SPI_getvalue` text → injected back via `quote_literal`.
  Potential precision/encoding loss. [verified-by-code]
  **[ISSUE-correctness: cascade-UPDATE round-trips values through
  text (maybe)]**
- **INV-4: `check_foreign_key` allocates `nrefs` SPI plans** up-
  front but DOES NOT cache them across trigger invocations. Each
  trigger fire re-runs `SPI_prepare` for every referencing table.
  Real FK uses `RI_FKey_setup` cache. [verified-by-code] `:366,
  462-467` **[ISSUE-correctness: plan churn per row (maybe — fine
  for tutorial)]**
- **INV-5: Both functions REQUIRE AFTER-ROW trigger timing**
  (`TRIGGER_FIRED_AFTER`). Comments don't explain why — but it's
  because the row mutation must be visible inside the same
  transaction for the SPI SELECT to see consistent state (vs
  BEFORE, where parent row deletion hasn't applied yet). [inferred]
  **[ISSUE-doc-drift: AFTER-ROW requirement not explained in
  comments (nit)]**
- **INV-6: DELETE on child / INSERT on parent are explicitly
  rejected.** `check_primary_key` errors on DELETE because there's
  no "incoming key" to validate. `check_foreign_key` errors on
  INSERT for the same symmetric reason. [verified-by-code] `:80-83,
  250-253`

## Potential issues

- `:117-125` Manual `SPI_fnumber` → column-not-found check passes
  the error through `ereport(ERROR, errcode(ERRCODE_UNDEFINED_COLUMN))`
  — proper user-facing error. Compare to `autoinc.c` which uses
  `ERRCODE_TRIGGERED_ACTION_EXCEPTION` for the same condition.
  Inconsistent across the spi/ tutorials. [verified-by-code]
  **[ISSUE-style: inconsistent errcode for "column not found" across
  tutorials (nit)]**
- `:281` `pg_strtoint32(args[0])` parses `nrefs` from a trigger
  string argument. No range check beyond signed int32; a negative
  or zero nrefs is caught by the next `if (nrefs < 1)`. OK.
  [verified-by-code]
- `:528` `elog(NOTICE, "..." UINT64_FORMAT, SPI_processed, ...)`
  is under `#ifdef REFINT_VERBOSE` — i.e. compile-time toggle. So
  the NOTICEs never reach production builds unless someone
  hand-edits. [verified-by-code]
  **[ISSUE-stale-todo: `REFINT_VERBOSE` is a debug knob with no
  build-time switch (nit)]**
- `:54-56, 232-234` `DEBUG_QUERY` is another compile-time toggle for
  `elog(DEBUG4, ...)`. Could be a runtime GUC instead.
  [verified-by-code] **[ISSUE-stale-todo: `DEBUG_QUERY` is
  compile-time only (nit)]**
- `:349` `if (oldval == NULL)` → "this shouldn't happen!
  SPI_ERROR_NOOUTFUNC?" then `elog(ERROR, ...)`. Exclamation
  marks and question marks in error text are tutorial-style. [verified-by-code]
- `:539` (post-EOF): no `SPI_finish` cleanup in the early-return
  paths at `:137, 335` — but those paths explicitly call
  `SPI_finish()` first. Good. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `spi`](../../../issues/spi.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [idioms/spi.md](../../../idioms/spi.md)
