---
path: src/interfaces/ecpg/include/decimal.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 13
depth: read
---

# `decimal.h` — Informix `dec_t` compatibility alias

## Purpose
Informix ESQL/C compatibility shim. Includes [[ecpg_informix.h]] and typedefs
`dec_t` = `decimal` (the fixed-array decimal struct from [[pgtypes_numeric.h]]),
the name Informix programs use — unless ecpglib already provided it.
[verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `typedef decimal dec_t` | decimal.h:10 | under `#ifndef _ECPGLIB_H` only [verified-by-code] |

## Invariants & gotchas
- Same inclusion-order subtlety as [[datetime.h]]: the `#ifndef _ECPGLIB_H`
  guard (decimal.h:9) suppresses the typedef when [[ecpglib.h]] is already in
  scope, because the ecpg-generated source defines it. [verified-by-code]
- `dec_t` is the *fixed* `digits[DECSIZE]` variant (`decimal`), not the malloc'd
  `numeric` — Informix decimal columns are bounded at DECSIZE=30 digit-groups.
  [verified-by-code]

## Cross-refs
- [[ecpg_informix.h]] — declares the `dec*` Informix decimal routines.
- [[pgtypes_numeric.h]] — the `decimal` struct `dec_t` aliases.
- [[datetime.h]] — sibling Informix shim for `dtime_t`/`intrvl_t`.
