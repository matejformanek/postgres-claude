# src/common/encnames.c

## Purpose

Encoding-name registry. Maps free-form encoding names from the wire
(`SET client_encoding TO 'UTF-8'`, etc.) to internal `pg_enc`
values, and the reverse direction for display.

## Role in PG

Shared **frontend + backend**. Backend uses it for
`SET client_encoding`, the startup packet's `client_encoding`
parameter, and `CREATE DATABASE ... ENCODING`. Frontend (libpq) uses
it for `PQsetClientEncoding`. The tables here are the single source
of truth for spelling variants like `UTF-8` vs `UTF8` vs `unicode`.

## Key data

- `pg_encname_tbl[]` — the alphabetic alias table (~75 entries).
  Sorted alphabetically; binary-searched.
  (`encnames.c:39-296`)
- `pg_enc2name_tbl[]` — the canonical reverse map, sparse-indexed
  by `pg_enc` enum value, also carries the Windows codepage number.
  (`encnames.c:308-351`)
- `pg_enc2gettext_tbl[]` — gettext-spelling reverse map.
  (`encnames.c:357-400`)
- `pg_enc2icu_tbl[]` static — ICU-spelling reverse map; NULL entry
  means ICU does not support that encoding.
  (`encnames.c:410-446`)

## Key functions

- `bool is_encoding_supported_by_icu(int encoding)`
  (`encnames.c:456-461`)
- `const char *get_encoding_name_for_icu(int encoding)`
  (`encnames.c:467-472`)
- `int pg_valid_client_encoding(const char *name)` — name → enum,
  rejected if not valid as a client encoding.
  (`encnames.c:479-491`)
- `int pg_valid_server_encoding(const char *name)` — same for
  server encoding. (`encnames.c:493-505`)
- `int pg_valid_server_encoding_id(int encoding)` — bool-ish check.
  (`encnames.c:507-511`)
- `clean_encoding_name(const char *key, char *newkey)` static —
  strips non-alphanumeric chars and lower-cases the rest (ASCII
  only). Caller must provide buffer ≥ NAMEDATALEN.
  (`encnames.c:519-536`)
- `int pg_char_to_encoding(const char *name)` — the real lookup.
  Rejects empty input and `strlen(name) >= NAMEDATALEN`. Cleans
  the name, then binary-searches `pg_encname_tbl`. Returns -1 if
  not found. (`encnames.c:544-579`)
- `const char *pg_encoding_to_char(int encoding)` — reverse map,
  returns `""` on out-of-range. (`encnames.c:582-592`)

## State / globals

Four read-only arrays. The ICU table has a
`StaticAssertDecl(lengthof(pg_enc2icu_tbl) == PG_ENCODING_BE_LAST + 1)`
guard at `encnames.c:448-449`.

## Phase D notes

- **Length bound is hard.** `pg_char_to_encoding` rejects anything
  `>= NAMEDATALEN` (currently 64) at line 557-558 BEFORE doing any
  copying or matching, so a hostile client cannot push a giant
  encoding name through to inflate `clean_encoding_name`.
  `[verified-by-code]`
- **Alias collisions exist by design.** `unicode` → `PG_UTF8`,
  `koi8` (no -R/-U) → `PG_KOI8R`, `win` → `PG_WIN1251`. These are
  flagged in the table as `"_dirty_" alias` comments — backward
  compat with very old client code. No security implication, just
  surprising behaviour if a user expected case-strict matching.
- **The alphabetic table must stay sorted** for `pg_char_to_encoding`
  to work; no compile-time check enforces this, only the comment at
  `encnames.c:22-27`. Adding an out-of-order entry would silently
  cause missed matches.

## Potential issues

`[ISSUE-undocumented-invariant: pg_encname_tbl[] alphabetic sort is
asserted only by comment; a misplaced entry would silently break the
binary search. A StaticAssertDecl-like check would catch this.
(low)]`

`[ISSUE-correctness: "_dirty_" aliases (unicode→UTF8, win→WIN1251,
koi8→KOI8R) are accepted in all contexts including CREATE DATABASE.
Documented as "backward compatibility" but never deprecated. (low)]`
