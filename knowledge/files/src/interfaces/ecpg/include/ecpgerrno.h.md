---
path: src/interfaces/ecpg/include/ecpgerrno.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 82
depth: read
---

# `ecpgerrno.h` — ECPG runtime error-code constants

## Purpose
The complete numeric `ECPG_*` error/warning code list an embedded-SQL program
can see in `sqlca.sqlcode`. Organized in bands: `0` no-error, `100`
not-found, `-ENOMEM` for OOM, `-200…` ecpglib-internal errors, `-220/-221`
connection errors, `-230` invalid statement, `-240…` dynamic-SQL/descriptor
errors, `-400…` backend-relayed errors, and `-600…` backend warnings.
[verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `ECPG_NO_ERROR` / `ECPG_NOT_FOUND` | ecpgerrno.h:9-10 | `0` / `100` (SQL `SQLNOTFOUND`) [verified-by-code] |
| `ECPG_OUT_OF_MEMORY` | ecpgerrno.h:16 | `-ENOMEM` (system errno made negative) [verified-by-code] |
| `ECPG_UNSUPPORTED … ECPG_ARRAY_INSERT` | ecpgerrno.h:19-35 | `-200…-216` ecpglib internal [verified-by-code] |
| `ECPG_NO_CONN` / `ECPG_NOT_CONN` | ecpgerrno.h:37-38 | `-220` / `-221` [verified-by-code] |
| `ECPG_UNKNOWN_DESCRIPTOR …` | ecpgerrno.h:43-47 | `-240…-244` dynamic SQL [verified-by-code] |
| `ECPG_PGSQL … ECPG_SUBSELECT_NOT_ONE` | ecpgerrno.h:50-54 | `-400…-404` backend-relayed [verified-by-code] |
| `ECPG_INFORMIX_DUPLICATE_KEY` / `..._SUBSELECT_NOT_ONE` | ecpgerrno.h:60-61 | `-239` / `-284` compat aliases [verified-by-code] |
| `ECPG_WARNING_* ` | ecpgerrno.h:64-80 | `-600…-605` backend warnings [verified-by-code] |

## Internal landmarks
- The `-ENOMEM` trick (ecpgerrno.h:13-16): system errnos are relayed as their
  negative, so a sqlcode `< -200` band is reserved for ecpg's own messages while
  `-1…-199` mirror C library errnos. [from-comment]
- The Informix-compat duplicates (ecpgerrno.h:56-61) deliberately give a
  *different* code to the same logical error for Informix-mode programs; the
  comment warns "make sure to not double define it". [from-comment]

## Invariants & gotchas
- These constants are the documented runtime contract; numeric values are part
  of the ABI shipped apps switch on — do not renumber. [inferred]
- The `-600` warning band lands in `sqlca.sqlcode` as a *negative* value even
  though they are warnings (not errors); programs that test `sqlcode < 0` as
  "error" will misclassify transaction-state warnings. [verified-by-code]

## Cross-refs
- [[sqlca.h]] — these land in `sqlca.sqlcode`.
- [[pgtypes_error.h]] — the disjoint `PGTYPES_*` (300-band) errors for the
  type library.
- `knowledge/files/src/interfaces/ecpg/ecpglib/error.c.md` — maps these to
  SQLSTATE + message text.
