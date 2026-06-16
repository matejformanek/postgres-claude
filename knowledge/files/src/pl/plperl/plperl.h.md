---
path: src/pl/plperl/plperl.h
anchor_sha: 4b0bf0788b0
loc: 206
---

# plperl.h

- **Source path:** `source/src/pl/plperl/plperl.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 206

## One-line summary

Internal-use header that (a) re-exports the C-callable SPI bridge
declared in `plperl.c` so `SPI.xs` / `Util.xs` can call them, and
(b) supplies four `static inline` UTF-8/encoding conversion helpers
that are textually shared between the main translation unit and the
XS units. [verified-by-code, plperl.h:27-40, 50-204]

## Role in PG

This is the only header that `.xs` files in `src/pl/plperl/` include
to talk to plperl.c. It must be `#include`d *after* `postgres.h` and
the relevant system headers (plperl.h:6-8) because it pulls in
Perl's headers (via `plperl_system.h`) which collide with PG's
`*printf` and `_` macros.

## Public API / exports

C prototypes (called from `SPI.xs` and `Util.xs`)
[verified-by-code, plperl.h:27-40]:

- `HV *plperl_spi_exec(char *query, int limit)` — one-shot SPI
  exec returning a hashref with `status`, `processed`, optional
  `rows`.
- `void plperl_return_next(SV *)` — append a row to the current
  SRF's tuplestore.
- `SV *plperl_spi_query(char *)` — open an SPI cursor on an
  unparameterized query, return a cursor-name SV.
- `SV *plperl_spi_fetchrow(char *cursor_name)` — fetch one row,
  return a hashref or undef at end-of-set.
- `SV *plperl_spi_prepare(char *query, int argc, SV **argv)` — save
  a parameterized plan, return a plan-handle SV.
- `HV *plperl_spi_exec_prepared(char *query, HV *attr, int argc, SV **argv)`
  — execute a saved plan, with optional `{ limit => N }` attribute hash.
- `SV *plperl_spi_query_prepared(char *query, int argc, SV **argv)` —
  open a cursor on a saved plan.
- `void plperl_spi_freeplan(char *query)` — invalidate saved plan.
- `void plperl_spi_cursor_close(char *cursor_name)` — close cursor.
- `void plperl_spi_commit(void)` — atomic-context aware COMMIT.
- `void plperl_spi_rollback(void)` — atomic-context aware ROLLBACK.
- `char *plperl_sv_to_literal(SV *, char *fqtypename)` — escape an
  SV for SQL inclusion via the type's output function.
- `void plperl_util_elog(int level, SV *msg)` — bridge `elog($level, $msg)`
  in Perl down to PG's elog/ereport.

`static inline` helpers (textually included in every TU that pulls
this header):

- `utf_u2e(char *utf8_str, size_t len)` (plperl.h:50-62) — UTF-8 →
  current database encoding via `pg_any_to_server`; always returns a
  palloc'd copy.
- `utf_e2u(const char *str)` (plperl.h:69-81) — database encoding →
  UTF-8 via `pg_server_to_any`; always palloc'd.
- `sv2cstr(SV *sv)` (plperl.h:88-140) — robust SV-to-cstring path:
  copies the SV if it's readonly/typeglob/exotic (to dodge SvPVutf8's
  croak on `$^V` etc.); in SQL_ASCII databases skips UTF-8 demand to
  avoid invalid-byte errors; passes the Perl-side length to
  `utf_u2e` so embedded NULs survive into the conversion (but are
  then handed as a cstring to typinput callers — see below).
- `cstr2sv(const char *str)` (plperl.h:146-164) — newSVpv with
  UTF-8 flag set after `pg_server_to_any` conversion (skipped for
  SQL_ASCII).
- `croak_cstr(const char *str)` (plperl.h:174-204) — push the message
  through `croak_sv` (modern Perl) or fall back to assigning a UTF-8
  SV into `ERRSV` and calling `croak(NULL)` after using `mess()` to
  pre-append the error location (older Perl versions lose location
  info otherwise, per plperl.h:184-189).

## Key invariants

- INV-1: `utf_u2e` / `utf_e2u` always return a freshly-palloc'd
  buffer, even when `pg_any_to_server` / `pg_server_to_any` are a
  no-op (the inline tests `ret == utf8_str` / `ret == str` and forces
  a `pstrdup`). Callers may safely `pfree` the result.
  [verified-by-code, plperl.h:57-60, 76-79]
- INV-2: `sv2cstr` never croaks even on readonly/typeglob SVs
  because it makes a defensive copy first (plperl.h:107-118). The
  fallback path `SvREFCNT_inc_simple_void(sv)` matches a
  `SvREFCNT_dec(sv)` at line 137, balanced.
- INV-3: In a `SQL_ASCII` database, both `sv2cstr` and `cstr2sv`
  bypass UTF-8 conversion entirely (plperl.h:125-126, 154-155).
  This is the documented "byte soup" mode.
- INV-4: `croak_cstr` always croaks — it never returns
  (plperl.h:202 calls `croak(NULL)` which longjmps).

## Notable internals

### `sv2cstr` defensive-copy logic

The condition `SvREADONLY(sv) || isGV_with_GP(sv) || (SvTYPE(sv) >
SVt_PVLV && SvTYPE(sv) != SVt_PVFM)` (plperl.h:107-109) targets the
known-buggy SV types for `SvPVutf8`. The comment names them: typeglobs
and readonly objects like `$^V`. The workaround is a private
`newSVsv(sv)` copy, garbage-collected via `SvREFCNT_dec(sv)` at the
end. [from-comment, plperl.h:102-106]

### `croak_cstr` location-info dance

For Perl < the version that exposes `croak_sv`, the fallback
(plperl.h:184-202) uses `mess("%s", utf8_str)` to construct an SV
that *already* has the `at FILE line N.` suffix appended,
because the alternative — assigning to `ERRSV` then `croak(NULL)` —
appends location info too late (after stack pop) in some Perl
versions, losing it from the message users see.
[from-comment, plperl.h:184-189]

### `cstr2sv` SQL_ASCII branch

In SQL_ASCII mode the function returns the SV without setting
`SvUTF8_on`. Perl then treats it as a byte string. This means a
PL/Perl function that returns a non-ASCII string in a SQL_ASCII
database will not see UTF-8 flagging on its arguments either —
consistent behaviour both directions.

## Trusted vs untrusted boundary

These helpers run inside whichever interpreter is currently active
(trusted or untrusted). They are pure C — the opmask doesn't apply,
since opmask gates Perl-level op dispatch, not C-level Perl API
calls. The `SvPVutf8(sv, len)` call (plperl.h:128) and
`newSVsv` (plperl.h:110) are Perl API functions, not opcodes; they
work identically in both postures.

The conversion routines do not differentiate trust posture. This is
correct — text returned from a plperl function is converted with the
same encoding rules as text returned from a plperlu function, and the
database encoding gate is the only filter (and database-wide).

## Issues spotted (inline)

- [ISSUE-correctness: `sv2cstr`'s `len` is Perl's byte length but the
  result is treated as a NUL-terminated cstring by all callers — an
  embedded NUL in user data is silently truncated downstream in
  `InputFunctionCall(typinput, str)` (maybe)] —
  `source/src/pl/plperl/plperl.h:130-140`. The comment at plperl.h:131-134
  even acknowledges: "We use perl's length in the event we had an
  embedded null byte to ensure we error out properly" — but the
  cstring handed to typinput discards length and stops at the NUL.
  Whether this surfaces as "error out properly" depends entirely on
  the typinput implementation.
- [ISSUE-correctness: `cstr2sv` calls `newSVpv(utf8_str, 0)` (zero
  meaning "compute length with strlen") (plperl.h:159), so a
  PG-side cstring containing an embedded NUL — possible in `bytea`
  output? no, that goes through `byteaout` which hex-escapes — would
  be silently truncated at the NUL on the Perl side. For text types
  this is moot since cstrings can't contain NULs anyway. (nit)]
  `source/src/pl/plperl/plperl.h:155-159`
- [ISSUE-defense-in-depth: `static inline` makes these functions
  inline into every `.xs` translation unit; if a future Perl-headers
  change causes `SvPVutf8` to be macro-redefined incompatibly per
  TU, callers may end up with subtle ABI mismatches (nit)]
  `source/src/pl/plperl/plperl.h:50-204`
- [ISSUE-documentation: the inline functions are only documented by
  their one-paragraph comments; the SQL_ASCII byte-soup mode is a
  cross-cutting invariant that deserves a top-level header note
  (nit)] `source/src/pl/plperl/plperl.h:120-126, 153-155`

## Cross-references

- `source/src/pl/plperl/plperl.c` — declares the SPI bridge functions
  and is the only translation unit that *defines* them.
- `source/src/pl/plperl/plperl_system.h` — pulled in via
  `#include "plperl_system.h"` at plperl.h:25.
- `source/src/pl/plperl/SPI.xs`, `Util.xs` — the consumers that
  include this header.
- `source/src/include/mb/pg_wchar.h` — declares
  `pg_any_to_server` / `pg_server_to_any` / `GetDatabaseEncoding` /
  `PG_UTF8`. The `#include` at plperl.h:19 carries a comment noting
  it "defines free() by way of system headers, so must be included
  before perl.h" — a perl-vs-PG portability concern.

<!-- issues:auto:begin -->
- [Issue register — `plperl`](../../../../issues/plperl.md)
<!-- issues:auto:end -->
