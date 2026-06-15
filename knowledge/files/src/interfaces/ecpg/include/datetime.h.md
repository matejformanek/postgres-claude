---
path: src/interfaces/ecpg/include/datetime.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 14
depth: read
---

# `datetime.h` — Informix `dtime_t` / `intrvl_t` compatibility aliases

## Purpose
Tiny Informix ESQL/C compatibility shim. Includes [[ecpg_informix.h]] and
typedefs `dtime_t` = `timestamp` and `intrvl_t` = `interval` — the names
Informix programs expect — but only when ecpglib hasn't already provided them.
[verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `typedef timestamp dtime_t` | datetime.h:10 | under `#ifndef _ECPGLIB_H` only [verified-by-code] |
| `typedef interval intrvl_t` | datetime.h:11 | under `#ifndef _ECPGLIB_H` only [verified-by-code] |

## Invariants & gotchas
- The `#ifndef _ECPGLIB_H` guard (datetime.h:9) means: if the translation unit
  already included [[ecpglib.h]], these typedefs are suppressed because "source
  created by ecpg … defines these symbols" (datetime.h:8). So inclusion order
  with `ecpglib.h` changes what this header contributes. [verified-by-code]
- This is the C header a `.pgc` using Informix datetime types maps to; it is
  almost pure indirection over [[pgtypes_timestamp.h]]/[[pgtypes_interval.h]]
  via [[ecpg_informix.h]]. [verified-by-code]

## Cross-refs
- [[ecpg_informix.h]] — the real Informix surface this re-exports.
- [[decimal.h]] — sibling Informix shim for `dec_t`.
