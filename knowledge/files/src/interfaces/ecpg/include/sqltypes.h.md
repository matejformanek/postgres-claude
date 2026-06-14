---
path: src/interfaces/ecpg/include/sqltypes.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 59
depth: read
---

# `sqltypes.h` — Informix `C*TYPE` / `SQL*` type-code aliases

## Purpose
Maps the Informix ESQL/C type-name constants onto ECPG's `ECPGt_*` codes. Two
groups: the `C*TYPE` host-variable codes (`CCHARTYPE`, `CINTTYPE`, …) and the
`SQL*` codes that go into `sqlda->sqlvar[i]->sqltype` (`SQLCHAR`, `SQLINT`,
`SQLDECIMAL`, …). Codes ECPG has no equivalent for get raw Informix numbers
(e.g. `CMONEYTYPE 111`, `CFILETYPE 116`). [verified-by-code]

## Public symbols
| Symbol group | Site | Notes |
|---|---|---|
| `C*TYPE` aliases | sqltypes.h:6-30 | host-var codes → `ECPGt_*` or literal Informix numbers [verified-by-code] |
| `CTYPEMAX` | sqltypes.h:30 | `25` [verified-by-code] |
| `SQL*` aliases | sqltypes.h:35-54 | sqlda `sqltype` codes → `ECPGt_*` [verified-by-code] |
| `SQLINT8` / `SQLSERIAL8` | sqltypes.h:49-54 | resolve to `ECPGt_long` or `ECPGt_long_long` by `SIZEOF_LONG` [verified-by-code] |

## Internal landmarks
- Many Informix codes collapse onto the same ECPG type: `SQLTEXT`, `SQLVCHAR`,
  `SQLNCHAR`, `SQLNVCHAR` all → `ECPGt_char` (sqltypes.h:44-48); `SQLFLOAT` →
  `ECPGt_double` while `SQLSMFLOAT` → `ECPGt_float` (sqltypes.h:38-39). [verified-by-code]
- Codes with no ECPG analogue keep literal Informix numbers: `CFIXCHARTYPE 108`,
  `CMONEYTYPE 111`, `CLOCATORTYPE 113`, `CINVTYPE 115`, etc. (sqltypes.h:13-29).
  These are accepted as ABI placeholders but not necessarily handled. [verified-by-code]

## Invariants & gotchas
- `SQLINT8`/`SQLSERIAL8` are resolved **at compile time** via `SIZEOF_LONG` /
  `SIZEOF_LONG_LONG`, and `#error` if neither is 8 bytes (sqltypes.h:49-57) —
  so the meaning of an 8-byte Informix int code depends on the client platform's
  `long` width. [verified-by-code]
- This header is the Informix-mode bridge into [[ecpgtype.h]]; renumbering
  `ECPGttype` would silently change these aliases' meaning. [inferred]

## Cross-refs
- [[ecpgtype.h]] — the `ECPGt_*` codes these alias.
- [[sqlda-compat.h]] — `sqlvar.sqltype` holds these `SQL*` values.
- [[ecpg_informix.h]] — the Informix mode that makes these relevant.
