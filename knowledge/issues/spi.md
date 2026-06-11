# Issues — `contrib/spi`

Tutorial-example trigger functions illustrating use of the
`SPI_*` tuple helpers and (for `refint.c`) full
`SPI_connect`/`SPI_prepare`/`SPI_execp`/`SPI_finish` patterns.
4 source files / ~896 LOC.

**Parent docs:** `knowledge/files/contrib/spi/*` (4 docs:
`autoinc.c.md`, `insert_username.c.md`, `moddatetime.c.md`,
`refint.c.md`).

**Source:** ~14 entries surfaced 2026-06-11 by A21-B.

## What these files teach (overall)

- **`autoinc.c`** — BEFORE-row trigger calling `DirectFunctionCall1(nextval, ...)` for
  INT4-from-sequence. Demonstrates `SPI_fnumber`/`SPI_gettypeid`/
  `SPI_getbinval` WITHOUT `SPI_connect` (these helpers don't need it
  since they're tuple-level wrappers).
- **`insert_username.c`** — Audit-stamp BEFORE-row trigger using
  `GetUserId()` + `GetUserNameFromId()`.
- **`moddatetime.c`** — BEFORE-row UPDATE trigger setting
  TIMESTAMP/TIMESTAMPTZ via `DirectFunctionCall3(timestamp_in,
  CStringGetDatum("now"), ...)`.
- **`refint.c`** — Two AFTER-row functions
  (`check_primary_key`, `check_foreign_key`) implementing FK
  semantics ENTIRELY in SPI: `SPI_connect`, `SPI_prepare`,
  `SPI_execp`, `SPI_finish`, with restrict/cascade/setnull
  actions. The canonical PG demo of in-trigger SPI usage.

## Headlines

1. **`refint.c::check_foreign_key` compares old/new keys as STRINGS
   via `SPI_getvalue`.** UPDATE-no-key-change detection uses
   `strcmp(oldval, newval)`. Wrong for any type whose text
   representation isn't canonical: NUMERIC with trailing zeros,
   JSONB with different formatting, BYTEA encoding choices, etc.
   Could cascade or fail to cascade incorrectly.
2. **`refint.c` cascade-UPDATE round-trips values through
   text.** `quote_literal_cstr` is used to inline new key values into
   SET clauses, since SET-values aren't parameter-bound. Potential
   precision loss for floats / locale-encoding hazards.
3. **`refint.c` re-`SPI_prepare`s on every trigger firing** — no
   plan caching across rows. Tutorial code; real `RI_FKey_setup`
   caches. Performance, not correctness.
4. **`autoinc.c` retries `nextval` only ONCE if it returns 0** —
   pathological sequence wrap or start-at-zero could yield 0 anyway.

## Entries — `autoinc.c`

- [ISSUE-doc-drift: only `!isnull && val != 0` is "needs autoinc"; zero treated as fill-me-in (nit)] — `:94-98`
- [ISSUE-correctness: single retry on `nextval` returning 0 (nit)] — `:106-110`
- [ISSUE-style: errmsg capitalization not PG-house style ("even number gt 0...") (nit)] — `:65`

## Entries — `insert_username.c`

- [ISSUE-doc-drift: docs may say "session user" but code uses CURRENT user via `GetUserId()` (nit)] — `:85`
- [ISSUE-style: inconsistent error-prefix convention vs `autoinc.c` (nit)] — `:42-48`

## Entries — `moddatetime.c`

- [ISSUE-doc-drift: `"now"` resolves to transaction-time, not statement/clock time — undocumented (nit)] — `:106-114`
- [ISSUE-question: typmod=−1 in `DirectFunctionCall3(timestamp_in, ...)` interaction with column TYPMOD (nit)] — `:106-114`
- [ISSUE-style: error-prefix inconsistency across spi/ tutorials (nit)] — `:50-58`

## Entries — `refint.c`

- [ISSUE-correctness: text-based key-change detection via `strcmp(SPI_getvalue, SPI_getvalue)` fails for types with non-canonical out-text (likely)] — `:341-355`
- [ISSUE-correctness: cascade-UPDATE round-trips values through text via `quote_literal_cstr` (maybe)] — `:415-427`
- [ISSUE-correctness: SPI plan re-prepared on every trigger fire; no cache (maybe — tutorial)] — `:366, 462-467`
- [ISSUE-doc-drift: AFTER-ROW requirement not explained in comments (nit)] — `:72-74, 255-257`
- [ISSUE-stale-todo: `REFINT_VERBOSE` and `DEBUG_QUERY` are compile-time-only debug switches (nit)] — `:54-56, 520-530`
- [ISSUE-style: inconsistent errcode for "column not found" vs other spi/ tutorials (nit)] — `:122-125`
