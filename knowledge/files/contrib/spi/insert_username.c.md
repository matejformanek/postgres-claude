# `contrib/spi/insert_username.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 95
- **Source:** `source/contrib/spi/insert_username.c`

Tutorial-example trigger function that overwrites one TEXT column with
the current session user's name on INSERT/UPDATE. Audit-style usage.
Like `autoinc.c` it doesn't actually use `SPI_connect`; only the
tuple-level SPI utilities (`SPI_fnumber`, `SPI_gettypeid`,
`SPI_getrelname`). [verified-by-code]

## API / entry points

- `insert_username(PG_FUNCTION_ARGS)` `:24-95` — sole entry point.
  BEFORE-ROW trigger on INSERT or UPDATE, single argument: the column
  name to overwrite. [verified-by-code]

## The pattern (what this file teaches)

1. **`GetUserId()` then `GetUserNameFromId(oid, false)`** is the
   canonical way to get the SESSION user's name (NOT the role they
   `SET ROLE`'d to — that would be `GetSessionUserId()`).
   Wait: actually `GetUserId()` returns the *current* user
   (CURRENT_USER, post-`SET ROLE`). [verified-by-code]
2. **`CStringGetTextDatum`** for converting a C string to TEXT
   datum. `:85` [verified-by-code]
3. **Type check is `SPI_gettypeid(tupdesc, attnum) != TEXTOID`** —
   no polymorphism, no implicit cast. `:78-82` [verified-by-code]
4. Same trigger-guard pattern as `autoinc.c`. [verified-by-code]

## Notable invariants / details

- **INV-1: `GetUserId()` returns the CURRENT user** (post-`SET ROLE`),
  not the SESSION user. The function name "insert_username" is a bit
  misleading — `SET ROLE bob; INSERT ...` records `bob`, not the
  authenticated session user. [verified-by-code]
  **[ISSUE-doc-drift: docs may say "session user" but code uses
  current user (nit)]**
- **INV-2: Target column type MUST be TEXT.** No `VARCHAR`, no
  `NAME`, no `CHAR(N)`. [verified-by-code]
- **INV-3: Comment at `:39` says "sanity checks from autoinc.c"** —
  cut and paste from `autoinc.c`. So fixing one to use ereport over
  elog means fixing both. [from-comment]

## Potential issues

- `:85` `GetUserNameFromId(GetUserId(), false)` returns a string
  allocated in `CurrentMemoryContext` (the per-call SPI/trigger
  context). It's NOT explicitly freed; the trigger calling context
  cleans it up. Fine in practice. [verified-by-code]
- `:42-48` Error messages prefix with `"insert_username: "` —
  inconsistent with `autoinc.c` which uses `"autoinc (%s): "` (with
  the relation name interpolated). Just style. [verified-by-code]
  **[ISSUE-style: inconsistent error-prefix convention across spi/
  examples (nit)]**
- No handling of NULL column value before overwrite — always
  overwrites, even on existing INSERT with explicit value. That's
  audit-style by design, not a bug. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `spi`](../../../issues/spi.md)
<!-- issues:auto:end -->
