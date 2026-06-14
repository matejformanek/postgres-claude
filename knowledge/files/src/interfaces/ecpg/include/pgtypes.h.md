---
path: src/interfaces/ecpg/include/pgtypes.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 17
depth: read
---

# `pgtypes.h` — pgtypeslib root header

## Purpose
The common root header for the standalone pgtypes library. Declares a single
symbol — `PGTYPESchar_free` — and is pulled in by every other `pgtypes_*.h`
header so the library has one canonical deallocator for the `char *` strings its
`*_to_asc` routines return. [verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `void PGTYPESchar_free(char *ptr)` | pgtypes.h:11 | frees strings returned by `PGTYPES*_to_asc` [verified-by-code] |

## Invariants & gotchas
- The reason this exists as a distinct call (rather than telling apps to use
  `free`) is the Windows multi-CRT problem: memory allocated inside the library's
  DLL must be freed by the library's allocator, not the app's. Apps **must** use
  `PGTYPESchar_free`, not `free()`, on returned strings. [inferred]
- Wrapped in `extern "C"` for C++ callers (pgtypes.h:6-9). [verified-by-code]

## Cross-refs
- [[pgtypes_numeric.h]], [[pgtypes_date.h]], [[pgtypes_timestamp.h]],
  [[pgtypes_interval.h]] — all `#include <pgtypes.h>`.
