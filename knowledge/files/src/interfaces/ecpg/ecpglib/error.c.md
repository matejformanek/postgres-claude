---
path: src/interfaces/ecpg/ecpglib/error.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 346
depth: deep
---

# `error.c` — ecpglib error reporting: maps libpq + internal errors onto the `sqlca` struct

## Purpose
This file is ecpglib's single funnel for turning two kinds of failures —
ecpg-internal conditions (bad argument count, type mismatch, out of memory,
etc.) and server/libpq errors — into the SQL-standard `sqlca_t` communication
area that an embedded-SQL program inspects after each statement. `ecpg_raise`
handles internal `ECPG_*` codes: it sets `sqlca->sqlcode`, copies a hard-coded
five-char SQLSTATE into `sqlca->sqlstate`, and `snprintf`s a localized message
into the fixed-width `sqlca->sqlerrm.sqlerrmc` buffer (error.c:24-209).
`ecpg_raise_backend` handles a `PGresult`/`PGconn` failure: it pulls SQLSTATE
and the primary message out of the result via `PQresultErrorField`, falls back
to `PQerrorMessage`/internal-error SQLSTATE when those are NULL, copies them
into the same `sqlca` fields, and derives a legacy `sqlcode` from a few special
SQLSTATEs (error.c:218-277). `ecpg_check_PQresult` is the per-result dispatcher
that decides which of the two raisers to call based on `PQresultStatus`
(error.c:280-330). `sqlprint` writes the current message to stderr
(error.c:333-346).

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `void ecpg_raise(int line, int code, const char *sqlstate, const char *str)` | error.c:12 | Populate `sqlca` for an internal `ECPG_*` code; big switch on `code` selects the translated message template |
| `void ecpg_raise_backend(int line, PGresult *result, PGconn *conn, int compat)` | error.c:218 | Populate `sqlca` from a server/libpq error; extracts SQLSTATE + message, derives legacy `sqlcode` |
| `bool ecpg_check_PQresult(PGresult *results, int lineno, PGconn *connection, enum COMPAT_MODE compat)` | error.c:280 | Inspect `PQresultStatus`; returns true on OK statuses, raises + `PQclear`s + returns false on errors |
| `void sqlprint(void)` | error.c:333 | Print the current `sqlca` message to stderr (user-facing `SQLPRINT` directive) |

## Internal landmarks
- **The internal-code switch** (error.c:27-209): one `case ECPG_*` per condition,
  each calling `snprintf(..., sizeof(sqlca->sqlerrm.sqlerrmc), ecpg_gettext("...
  on line %d"), ...)`. The translator comment "this string will be truncated at
  149 characters expanded" is repeated on every case (error.c:31-33 etc.) and
  documents the deliberate cap. `default` emits a generic `"SQL error %d on line
  %d"` (error.c:204-207).
- **SQLSTATE copy** via `strncpy(sqlca->sqlstate, sqlstate, sizeof(sqlca->sqlstate))`
  (error.c:25, error.c:262). `sqlca->sqlstate` is `char[5]` and is *not*
  NUL-terminated by design; callers always treat it with an explicit width
  (see error.c:265-268, error.c:272-273).
- **libpq error extraction** (error.c:232-255): `PQresultErrorField(result,
  PG_DIAG_SQLSTATE)` and `PG_DIAG_MESSAGE_PRIMARY` return NULL for
  libpq-generated (client-side) errors; fallbacks are
  `ECPG_SQLSTATE_ECPG_INTERNAL_ERROR` and `PQerrorMessage(conn)`. A broken
  connection is special-cased to SQLSTATE `57P02` ("the connection to the server
  was lost") (error.c:250-254).
- **Legacy sqlcode mapping** (error.c:264-270): SQLSTATE `23505` →
  `ECPG_(INFORMIX_)DUPLICATE_KEY`, `21000` → `ECPG_(INFORMIX_)SUBSELECT_NOT_ONE`,
  else `ECPG_PGSQL`. `INFORMIX_MODE(compat)` selects the Informix-compat variant.
- **gettext / locale**: every user-facing format string is wrapped in
  `ecpg_gettext(...)` (error.c:33, :253, :345) so messages are localized.
- **`sqlerrml` bookkeeping**: both raisers set `sqlca->sqlerrm.sqlerrml =
  strlen(sqlca->sqlerrm.sqlerrmc)` after formatting (error.c:211, error.c:259);
  `sqlprint` uses that length to NUL-cap before printing (error.c:344).
- **NULL-sqlca guard**: every entry point checks `ECPGget_sqlca() == NULL`
  (allocation failure) and bails after `ECPGfree_auto_mem()` (error.c:17-22,
  :225-230, :338-342).

## Invariants & gotchas
- **`sqlca->sqlstate` is a fixed 5-byte, non-NUL-terminated field.** `strncpy`
  with `sizeof(sqlca->sqlstate)` (=5) is correct here precisely because the
  field is exactly 5 chars and downstream comparisons use width-bounded
  `strncmp` / `%.*s` (error.c:265-273). Never `strcmp`/`%s` it or assume a NUL.
  [verified-by-code] error.c:25, :262.
- **`sqlerrmc` is a fixed-width buffer and messages are silently truncated.**
  All writes use `snprintf` with `sizeof(sqlca->sqlerrm.sqlerrmc)` (error.c:30,
  :258, ...), so there is no overflow, but server message text longer than the
  buffer (~149 bytes after expansion per the translator note) is cut off. This
  is intentional and standard for `sqlca`. [verified-by-code]
- **Server message text is copied through `snprintf("%s on line %d", message,
  line)`** (error.c:258) — bounded by the buffer size, so no unbounded copy of
  attacker/server-controlled text. [verified-by-code]
- **`ecpg_check_PQresult` owns `PQclear` on the error/empty paths** (error.c:299,
  :310, :319, :326) but *not* on the success paths (PGRES_TUPLES_OK /
  COMMAND_OK / COPY_OUT return true without clearing) — the caller must clear
  there. [verified-by-code] error.c:293-329.
- **`ecpg_raise_backend(NULL, ...)` is legitimate.** When `results == NULL`
  (error.c:283-287) the backend raiser is called with a NULL `PGresult`;
  `PQresultErrorField(NULL, ...)` returns NULL and the fallbacks kick in. Do not
  add a non-NULL assertion. [verified-by-code]
- **errno is not touched here.** These functions do not read or preserve
  `errno`; they format from explicit args / libpq accessors. [inferred]
- **`PGRES_COPY_IN` is treated as an error**, calling `PQendcopy` and returning
  false (error.c:316-321) — ecpg never expects to be mid-COPY-IN at check time.
  [verified-by-code]

## Cross-refs
- [[execute.c]] — primary caller; runs statements and calls
  `ecpg_check_PQresult` on each result.
- [[connect.c]] — connection setup raises `ECPG_CONNECT` / `ECPG_NO_CONN` via
  `ecpg_raise`.
- [[misc.c]] — home of `ECPGget_sqlca`, `ecpg_log`, `ecpg_gettext`,
  `ECPGfree_auto_mem` used throughout this file.

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues
- **[ISSUE-infoleak: server message text surfaces in client `sqlca`]**
  `error.c:258` — `ecpg_raise_backend` copies the server's
  `PG_DIAG_MESSAGE_PRIMARY` (or `PQerrorMessage`) verbatim into the
  client-visible `sqlerrmc`. This is by-design SQL/ecpg behavior and the copy is
  length-bounded, so it is not a memory-safety bug; the only "side channel" is
  the ordinary one of error messages carrying server detail. Severity: low /
  informational — flagged only for completeness, no action implied.
