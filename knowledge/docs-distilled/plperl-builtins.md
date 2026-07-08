---
source_url: https://www.postgresql.org/docs/current/plperl-builtins.html
fetched_at: 2026-07-07T20:51:00Z
anchor_sha: 9d1188f29865
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/Perl built-in functions (§45.4) — the SPI wrappers + %_SHARED

How PL/Perl exposes the backend's SPI layer to Perl code, and the
memory/plan-lifetime semantics that make each call safe or a footgun. This is
the Perl-side twin of `spi.md` / the `fmgr-and-spi` skill.

## Non-obvious claims (SPI database access)

- **`spi_exec_query(query [, limit])` materializes the whole result.** Returns a
  hashref with `{rows}` (arrayref of column-name→value hashrefs), `{processed}`
  (row count) and `{status}`. Optional `limit` caps rows like SQL `LIMIT`. Use
  only for small results — the full set is loaded into memory. [from-docs]
- **`spi_query` / `spi_fetchrow` / `spi_cursor_close` stream.** `spi_query`
  returns a cursor; `spi_fetchrow` yields one row hashref at a time and returns
  `undef` when exhausted (which auto-frees the cursor). If you stop early you
  **must** `spi_cursor_close($cursor)` or you leak the cursor. This is the
  large-result path. [from-docs]
- **`spi_prepare(command, @arg_types)` → reusable plan.** Placeholders are
  `$1..$n`; pass a list of type names. The returned plan handle is executed with
  `spi_exec_prepared(plan [, \%attrs], @args)` (materializing, accepts
  `{limit => N}`) or `spi_query_prepared(plan, @args)` (cursor, drive with
  `spi_fetchrow`). Free with `spi_freeplan(plan)`. [from-docs]
- **Plans persist for the session; stash them in `$_SHARED` to reuse.** The
  idiom `$_SHARED{my_plan} //= spi_prepare(...)` survives across function
  re-invocations within the same interpreter. Not caching = re-planning every
  call. [from-docs]
- **`spi_commit()` / `spi_rollback()` are the ONLY way to do txn control** — you
  cannot run `COMMIT`/`ROLLBACK` through `spi_exec_query`. Callable only at the
  top level of a procedure or `DO` block (non-atomic context). A new transaction
  starts automatically afterward. [from-docs] (Same non-atomic-SPI mechanism the
  `plpgsql-transactions` / `spi-transaction` docs describe.)

## Utility built-ins

- **Quoting:** `quote_literal` (undef→undef), `quote_nullable`
  (undef→literal `NULL`), `quote_ident` (quotes only when necessary, doubling
  embedded quotes). [from-docs]
- **Bytea:** `encode_bytea` / `decode_bytea`. **Arrays:**
  `encode_array_literal(arr [, delim])` (default delim `", "`, §8.15.2 form) and
  `encode_array_constructor(arr)` (uses `quote_nullable`, §4.2.12 form).
  **Typed:** `encode_typed_literal(value, typename)` handles nested arrays +
  composites. [from-docs]
- **`elog(level, msg)`** with `DEBUG/LOG/INFO/NOTICE/WARNING/ERROR`; `ERROR`
  behaves like Perl `die` and aborts the (sub)transaction. Visibility follows
  `log_min_messages` / `client_min_messages`. [from-docs]
- **Predicates:** `looks_like_number` (treats `Inf`/`Infinity` as numeric,
  trims space, undef→undef); `is_array_ref` (true for `ARRAY` refs and
  `PostgreSQL::InServer::ARRAY`). [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/spi.md]] / [[knowledge/docs-distilled/spi-memory.md]]
  — the C SPI API these commands wrap; the "materialize vs cursor" split mirrors
  `SPI_execute` vs `SPI_cursor_*`.
- [[knowledge/docs-distilled/plperl-under-the-hood.md]] — `%_SHARED` lifetime +
  interpreter model.
- [[knowledge/docs-distilled/spi-transaction.md]] — the non-atomic-context rule
  behind `spi_commit`/`spi_rollback`.
