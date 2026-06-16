---
path: src/port/quotes.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 51
depth: deep
---

# src/port/quotes.c

## Purpose

Provides `escape_single_quotes_ascii(const char *src)` — doubles every single
quote and backslash in a string, returning a freshly `malloc`'d copy the caller
must `free`. Used to safely embed a value as a single-quoted string literal in
**configuration files**: `postgresql.conf` entries, and the recovery
configuration `pg_basebackup` writes (`primary_conninfo`, etc.). Because
`postgresql.conf` string parsing treats backslash as an escape, backslashes
must be doubled too. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `char *escape_single_quotes_ascii(const char *src)` | `quotes.c:33` | Returns `malloc`'d string (caller frees); `NULL` on `malloc` failure |

## Internal landmarks

- Allocation (`quotes.c:38`) — `malloc(len * 2 + 1)`, the worst case where every
  byte needs doubling.
- Doubling loop (`:43-48`) — for each input byte, if `SQL_STR_DOUBLE(c, true)`
  (single quote or backslash) emit the char twice, else once. The `true`
  argument means "treat backslash as an escape to be doubled".

## Invariants & gotchas

- **For config files only, not SQL.** The header comment is explicit: "Since
  this function is only used for parsing or creating configuration files, we do
  not care about encoding considerations" (`quotes.c:26-27`). It is **not** the
  right tool for SQL literal escaping — that is `appendStringLiteral` /
  `PQescapeStringConn`, which are encoding-aware. Misusing this for SQL on a
  multibyte client encoding could be an injection vector.
- Returns `malloc`'d (not `palloc`'d) memory — frontend-safe, but backend
  callers must `free`, not `pfree`.

## Potential issues

- **[ISSUE-correctness: int length truncation before malloc sizing]**
  `quotes.c:35,38` — `int len = strlen(src)` then `malloc(len * 2 + 1)`. If
  `src` exceeded `INT_MAX` bytes, `len` would be truncated/negative and the
  allocation undersized relative to the loop bound, risking a heap overflow.
  In practice inputs are short config-string values, so this is not reachable
  today, but the `int` truncation is an undocumented size assumption. Severity:
  nit. See `knowledge/issues/port.md`.

## Cross-refs

- `knowledge/files/src/fe_utils/recovery_gen.c.md` — writes recovery config,
  the primary consumer (secret-to-disk theme).
- `knowledge/idioms/safe-sql-identifiers.md` (proposed) — the SQL-side escaping
  helpers this is explicitly *not*.

<!-- issues:auto:begin -->
- [Issue register — `port`](../../../issues/port.md)
<!-- issues:auto:end -->
