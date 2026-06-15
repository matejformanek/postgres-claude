---
path: src/interfaces/ecpg/include/pgtypes_error.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 18
depth: read
---

# `pgtypes_error.h` — pgtypeslib error constants

## Purpose
The numeric error codes the standalone pgtypes library (`numeric` / `date` /
`timestamp` / `interval` conversion routines) sets in the global `errno`. Three
bands: numeric `301-304`, date `310-315`, timestamp `320-321`, interval `330`.
[verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `PGTYPES_NUM_OVERFLOW … _UNDERFLOW` | pgtypes_error.h:3-6 | `301-304` numeric [verified-by-code] |
| `PGTYPES_DATE_BAD_DATE … _BAD_MONTH` | pgtypes_error.h:8-13 | `310-315` date [verified-by-code] |
| `PGTYPES_TS_BAD_TIMESTAMP / _ERR_EINFTIME` | pgtypes_error.h:15-16 | `320-321` timestamp [verified-by-code] |
| `PGTYPES_INTVL_BAD_INTERVAL` | pgtypes_error.h:18 | `330` interval [verified-by-code] |

## Invariants & gotchas
- These are a **separate namespace** from the `ECPG_*` codes in [[ecpgerrno.h]]:
  pgtypeslib is usable standalone (without ecpglib), so it signals via `errno`
  set to these 300-band values rather than via `sqlca`. [inferred]
- Distinct again from the Informix `ECPG_INFORMIX_*` (`-12xx`) codes in
  [[ecpg_informix.h]] for the same conversion failures. Three parallel
  error vocabularies cover the same operations. [verified-by-code]

## Cross-refs
- `knowledge/files/src/interfaces/ecpg/pgtypeslib/` — numeric.c / dt_common.c /
  interval.c / timestamp.c set these.
- [[ecpg_informix.h]] — the `-12xx` Informix mirror codes.
