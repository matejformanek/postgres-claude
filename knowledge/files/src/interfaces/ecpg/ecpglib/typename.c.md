---
path: src/interfaces/ecpg/ecpglib/typename.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 145
depth: deep
---

# `typename.c` — ECPG host-variable type ⇄ name / SQL3 / Oid mappings

## Purpose
Three small switch-based lookups bridging ecpglib's host-variable type codes
(`enum ECPGttype`, the `ECPGt_*` values), PostgreSQL type Oids, and the SQL3
descriptor type codes. `ecpg_type_name` renders an `ECPGt_*` code as a C type
name string; `ecpg_dynamic_type` maps a PG Oid to a `SQL3_*` descriptor code;
`sqlda_dynamic_type` maps a PG Oid to the `ECPGt_*` host type used when filling
an SQLDA. [verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `const char *ecpg_type_name(enum ECPGttype typ)` | typename.c:17 | returns static C type-name string; `default: abort()` (typename.c:67) [verified-by-code] |
| `int ecpg_dynamic_type(Oid type)` | typename.c:73 | PG Oid → `SQL3_*` descriptor code; unhandled Oid → `0` (typename.c:102) [verified-by-code] |
| `int sqlda_dynamic_type(Oid type, enum COMPAT_MODE compat)` | typename.c:107 | PG Oid → `ECPGt_*`; INFORMIX mode picks `ECPGt_decimal` vs `ECPGt_numeric` for NUMERICOID (typename.c:125); unhandled → `ECPGt_char` (typename.c:143) [verified-by-code] |

## Internal landmarks
- `ecpg_type_name` collapses several codes: `ECPGt_char`/`ECPGt_string` →
  `"char"`, and `ECPGt_char_variable` → `"char"` (typename.c:21-23, 52-53). The
  trailing `return ""` after `abort()` exists only to keep MSVC happy
  (typename.c:69). [verified-by-code]
- `sqlda_dynamic_type` resolves INT8OID at compile time to `ECPGt_long` or
  `ECPGt_long_long` depending on `SIZEOF_LONG`/`SIZEOF_LONG_LONG`, and `#error`s
  if neither is 8 bytes (typename.c:133-140). [verified-by-code]

## Invariants & gotchas
- `ecpg_type_name` is the only one of the three that is NOT total: an unknown
  `ECPGttype` calls `abort()` (typename.c:67), crashing the client process. The
  other two have benign fall-through defaults (`0` / `ECPGt_char`). A new
  `ECPGt_*` code added elsewhere without a case here becomes a latent abort. [verified-by-code]
- `ecpg_dynamic_type` and `sqlda_dynamic_type` cover overlapping but not
  identical Oid sets — e.g. `sqlda_dynamic_type` handles INT8OID, INTERVALOID,
  TIMESTAMPTZOID, CHAROID which `ecpg_dynamic_type` does not. Do not assume one
  is a superset of the other. [verified-by-code]
- Time vs timestamp: `ecpg_dynamic_type` maps TIMEOID and DATEOID and
  TIMESTAMPOID all to `SQL3_DATE_TIME_TIMESTAMP` (typename.c:93-98); the SQL3
  code does not distinguish them. [verified-by-code]

## Cross-refs
- [[ecpglib_extern.h]] — prototypes; `enum COMPAT_MODE`, `INFORMIX_MODE` macro.
- [[descriptor.c]] / [[sqlda.c]] — consumers of `ecpg_dynamic_type` /
  `sqlda_dynamic_type` when building descriptors. [inferred]
- `ecpgtype.h` — defines `enum ECPGttype`; `sql3types.h` defines `SQL3_*`.

## Potential issues
- `ecpg_type_name`'s `abort()` on an unrecognized `ECPGttype` (typename.c:67) is
  a hard crash of the linked client application rather than a raised ecpg error.
  It is reachable only if an `ECPGt_*` value is passed that this switch omits, so
  in practice it guards an internal invariant; flagged low-severity because it is
  not reachable from well-formed preprocessor output. [inferred]
