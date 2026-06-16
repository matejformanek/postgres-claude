---
path: src/interfaces/ecpg/include/sqlda-native.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 43
depth: read
---

# `sqlda-native.h` — native PostgreSQL SQLDA layout

## Purpose
Defines the native (non-Informix) SQLDA structs used for dynamic-SQL result
description: `struct sqlname` (length + 64-byte name), `struct sqlvar_struct`
(per-column type/len/data/indicator/name), and `struct sqlda_struct` (the
descriptor header with a `sqlvar[1]` flexible-array tail). [verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `NAMEDATALEN` | sqlda-native.h:16 | `64` — client copy of the server's identifier cap [verified-by-code] |
| `struct sqlname` | sqlda-native.h:18 | `short length` + `char data[NAMEDATALEN]` [verified-by-code] |
| `struct sqlvar_struct` | sqlda-native.h:24 | sqltype/sqllen/sqldata/sqlind/sqlname [verified-by-code] |
| `struct sqlda_struct` | sqlda-native.h:33 | sqldaid[8]/sqldabc/sqln/sqld/desc_next + `sqlvar[1]` [verified-by-code] |

## Internal landmarks
- `sqlvar[1]` (sqlda-native.h:40) is the classic pre-C99 flexible array member:
  the descriptor is allocated with `sizeof(sqlda_struct) + (n-1)*sizeof(sqlvar)`
  so `sqlvar[]` over-indexes into the allocation. [verified-by-code]
- `sqln` = allocated slots, `sqld` = filled columns (sqlda-native.h:37-38) — the
  standard SQLDA distinction. [from-comment]

## Invariants & gotchas
- **`NAMEDATALEN` is hardcoded to 64** with the comment that it "should be at
  least as much as NAMEDATALEN of the database the applications run against"
  (sqlda-native.h:8-16). A server built with a larger `NAMEDATALEN` will have
  column/table names **silently truncated** into `sqlname.data` on the client.
  [verified-by-code] See `knowledge/issues/ecpg.md`.
- The `sqlvar[1]` over-allocation idiom is correct but fragile: any code that
  `sizeof`s the struct to size an allocation, instead of using the
  `(n-1)*sizeof` form, under-allocates. [inferred]

## Cross-refs
- [[sqlda.h]] — selects this layout in non-Informix mode.
- [[sqlda-compat.h]] — the (incompatible) Informix layout.
- `knowledge/files/src/interfaces/ecpg/ecpglib/sqlda.c.md` — fills these.

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues
- **[ISSUE-invariant: client NAMEDATALEN may lag server]** `sqlda-native.h:16` —
  hardcoded `NAMEDATALEN 64`; a server with a larger value truncates identifier
  names placed into the SQLDA with no error. Mirrored to `knowledge/issues/ecpg.md`.
