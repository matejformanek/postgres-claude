---
path: src/interfaces/ecpg/include/pgtypes_interval.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 40
depth: read
---

# `pgtypes_interval.h` — client-side interval type API

## Purpose
Defines the client `interval` struct (an `int64 time` + `long month`) and the
`PGTYPESinterval_*` API. Also the canonical place the pgtypes library typedefs
`int64` (as `int64_t`) and forces `HAVE_INT64_TIMESTAMP` on, for clients that
don't pull in the backend's `c.h`. [verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `typedef int64_t int64` | pgtypes_interval.h:13 | only under `#ifndef C_H` [verified-by-code] |
| `struct interval` | pgtypes_interval.h:19 | `int64 time` (sub-month units) + `long month` [verified-by-code] |
| `PGTYPESinterval_new/_free` | pgtypes_interval.h:30-31 | lifecycle [verified-by-code] |
| `PGTYPESinterval_from_asc/_to_asc` | pgtypes_interval.h:32-33 | text I/O [verified-by-code] |
| `PGTYPESinterval_copy` | pgtypes_interval.h:34 | deep copy [verified-by-code] |

## Internal landmarks
- The `#ifndef C_H` guard (pgtypes_interval.h:11-17) lets the header coexist with
  the backend `c.h`: if `c.h` already defined `int64` / `C_H`, this skips the
  typedef. So including pgtypeslib headers *after* backend headers is safe; the
  client-only path defines `int64` itself. [verified-by-code]
- `month` is placed *after* `time` "for alignment" (pgtypes_interval.h:22). [from-comment]

## Invariants & gotchas
- `HAVE_INT64_TIMESTAMP` is `#define`d unconditionally in an **installed public
  header** (pgtypes_interval.h:15) — a legacy macro now always-true upstream but
  still exposed to app preprocessors; could collide with an app's own
  definition. [verified-by-code]
- `interval.month` is `long` (pgtypes_interval.h:22): width differs LP64 vs
  LLP64 (Win64), so the public struct size is platform-dependent. Same theme as
  `date` in [[pgtypes_date.h]]. [verified-by-code] See `knowledge/issues/ecpg.md`.

## Cross-refs
- [[pgtypes.h]] — `PGTYPESchar_free` for `_to_asc` results.
- [[pgtypes_timestamp.h]] — depends on `int64` + `interval` defined here.
- [[pgtypes_error.h]] — `PGTYPES_INTVL_BAD_INTERVAL`.
- `knowledge/files/src/interfaces/ecpg/pgtypeslib/interval.c.md`.
