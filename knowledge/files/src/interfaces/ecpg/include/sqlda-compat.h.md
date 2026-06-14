---
path: src/interfaces/ecpg/include/sqlda-compat.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 47
depth: read
---

# `sqlda-compat.h` — Informix-compatible SQLDA layout

## Purpose
Defines the wide, Informix-compatible SQLDA structs `struct sqlvar_compat` and
`struct sqlda_compat`. Each column carries the basic type/len/data/indicator
plus Informix extensions: a named indicator variable, extended type id/name,
owner name, source-type fields, and a `sqlilongdata` pointer for data exceeding
the legacy 32K limit. [verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `struct sqlvar_compat` | sqlda-compat.h:8 | ~20-field Informix column descriptor [verified-by-code] |
| `struct sqlda_compat` | sqlda-compat.h:37 | header: `sqld`/`sqlvar`/`desc_name[19]`/`desc_occ`/`desc_next` [verified-by-code] |

## Internal landmarks
- `sqlname` here is a plain `char *` (sqlda-compat.h:14), unlike the native
  layout's fixed `struct sqlname` — the two SQLDA families store column names
  differently. [verified-by-code]
- `sqlvar` in `sqlda_compat` is a `struct sqlvar_compat *` pointer
  (sqlda-compat.h:40), i.e. a separately-allocated array — *not* the
  flexible-array-tail idiom the native [[sqlda-native.h]] uses. [verified-by-code]
- `sqlilongdata` (sqlda-compat.h:32) is the post-32K-limit extension; `sqlilen`
  / `sqlidata` remain capped at <32K "for backward compatibility". [from-comment]

## Invariants & gotchas
- **Layout-incompatible with [[sqlda-native.h]]**: different field set, and
  `sqlvar` is a pointer-to-array vs a flexible tail. Code must commit to one
  SQLDA family (chosen by `_ECPG_INFORMIX_H` via [[sqlda.h]]) and never alias
  between them. [verified-by-code]
- `desc_name[19]` is a fixed 19-byte buffer (sqlda-compat.h:41) — descriptor
  names longer than 18 chars + NUL truncate. [verified-by-code]
- Several fields are explicitly "reserved for future use" / "for internal use
  only" (sqlda-compat.h:15,33-34); apps must not depend on them. [from-comment]

## Cross-refs
- [[sqlda.h]] — selects this layout when `_ECPG_INFORMIX_H` is set.
- [[sqlda-native.h]] — the native counterpart.
- `knowledge/files/src/interfaces/ecpg/ecpglib/sqlda.c.md`.
