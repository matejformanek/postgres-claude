---
path: src/interfaces/ecpg/include/sqlda.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 18
depth: read
---

# `sqlda.h` — SQLDA type selector (native vs Informix-compat)

## Purpose
A thin selector header: it typedefs `sqlvar_t` / `sqlda_t` to either the
Informix-compatible structs (from [[sqlda-compat.h]]) or the native PostgreSQL
structs (from [[sqlda-native.h]]), keyed on whether `_ECPG_INFORMIX_H` is
defined. [verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `sqlvar_t` / `sqlda_t` (Informix) | sqlda.h:7-8 | `struct sqlvar_compat` / `struct sqlda_compat` when `_ECPG_INFORMIX_H` [verified-by-code] |
| `sqlvar_t` / `sqlda_t` (native) | sqlda.h:13-14 | `struct sqlvar_struct` / `struct sqlda_struct` otherwise [verified-by-code] |

## Invariants & gotchas
- The branch is on `#ifdef _ECPG_INFORMIX_H` (sqlda.h:4) — set by including
  [[ecpg_informix.h]]. So the meaning of `sqlda_t` in a translation unit depends
  entirely on whether Informix mode was pulled in *before* this header. Mixing
  Informix-mode and native-mode SQLDA in one program is a layout-mismatch trap.
  [verified-by-code]
- The two struct families are **not** layout-compatible (compat has ~20 fields,
  native has 5) — see [[sqlda-compat.h]] vs [[sqlda-native.h]]. [verified-by-code]

## Cross-refs
- [[sqlda-compat.h]] — the Informix layout.
- [[sqlda-native.h]] — the native layout.
- [[ecpg_informix.h]] — defines the selecting macro.
