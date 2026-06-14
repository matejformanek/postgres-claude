---
path: src/interfaces/ecpg/include/sqlca.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 66
depth: read
---

# `sqlca.h` — the SQL Communications Area struct

## Purpose
Defines `struct sqlca_t`, the SQL-standard / Informix-compatible communications
area an embedded-SQL program inspects after each statement: `sqlcode`,
`sqlstate[5]`, the `sqlerrm` message (length + 150-byte buffer), the `sqlerrd[6]`
diagnostics array (element 1 = OID, element 2 = processed row count), and the
`sqlwarn[8]` warning flags. [verified-by-code] Accessed through the `sqlca`
macro, which expands to `(*ECPGget_sqlca())` so each thread sees its own area
(sqlca.h:58-60). [verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `struct sqlca_t` | sqlca.h:19 | the frozen ABI struct [verified-by-code] |
| `ECPGget_sqlca(void)` | sqlca.h:56 | returns the per-thread `sqlca_t *` [verified-by-code] |
| `sqlca` macro | sqlca.h:59 | `(*ECPGget_sqlca())` unless `POSTGRES_ECPG_INTERNAL` [verified-by-code] |
| `SQLERRMC_LEN` | sqlca.h:12 | 150 — fixed message buffer [verified-by-code] |

## Internal landmarks
- `sqlerrd` semantics are documented purely by comment (sqlca.h:31-38): index 1
  = OID of processed tuple, index 2 = rows processed by INSERT/UPDATE/DELETE;
  the rest are "empty". `sqlwarn[0]='W'` is the "some warning is set" rollup;
  `sqlwarn[1]='W'` flags string truncation into a host variable
  (sqlca.h:40-43). [from-comment]
- `PGDLLIMPORT` is self-defined here (sqlca.h:4-10) so the header is standalone
  on Windows without pulling in the backend's `c.h`. [verified-by-code]

## Invariants & gotchas
- `struct sqlca_t` is a **frozen on-the-wire/ABI layout** shared with Informix
  ESQL/C and shipped app binaries; field order, the `sqlcaid[8]` magic, and
  `SQLERRMC_LEN=150` cannot change without breaking compatibility. [inferred]
- `sqlerrmc` is a fixed 150-byte buffer (sqlca.h:27): backend error messages
  longer than that are truncated; `sqlerrml` carries the (possibly truncated)
  used length. Not a leak, but a known information-loss surface. [verified-by-code]
- `sqlstate` is `char[5]` — **not** NUL-terminated (sqlca.h:53). Callers must
  read exactly 5 bytes. [verified-by-code]

## Cross-refs
- [[ecpglib.h]] — `SQLCODE`/`SQLSTATE` macros read `sqlca.sqlcode`/`.sqlstate`.
- [[ecpgerrno.h]] — the negative `ECPG_*` codes that land in `sqlcode`.
- `knowledge/files/src/interfaces/ecpg/ecpglib/misc.c.md` — `ECPGget_sqlca`
  (per-thread sqlca via TLS).
